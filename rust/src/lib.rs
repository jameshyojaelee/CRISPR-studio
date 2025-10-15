use indexmap::IndexMap;
use numpy::PyReadonlyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use statrs::distribution::{Beta, ContinuousCDF};
use std::cmp::Ordering;

#[derive(Clone)]
struct GuideEntry {
    gene: String,
    value: f64,
    weight: f64,
}

#[derive(Clone)]
struct RraRecord {
    gene: String,
    score: f64,
    p_value: f64,
    fdr: f64,
    rank: usize,
    n_guides: usize,
    mean_log2fc: f64,
    median_log2fc: f64,
    var_log2fc: f64,
}

fn compute_ranks(entries: &[GuideEntry], higher_is_better: bool) -> Vec<f64> {
    let mut order: Vec<usize> = (0..entries.len()).collect();
    order.sort_by(|a, b| {
        let lhs = entries[*a].value;
        let rhs = entries[*b].value;
        match (lhs.is_nan(), rhs.is_nan()) {
            (true, true) => Ordering::Equal,
            (true, false) => Ordering::Greater,
            (false, true) => Ordering::Less,
            (false, false) => {
                if higher_is_better {
                    rhs.partial_cmp(&lhs).unwrap_or(Ordering::Equal)
                } else {
                    lhs.partial_cmp(&rhs).unwrap_or(Ordering::Equal)
                }
            }
        }
    });

    let mut ranks = vec![0.0; entries.len()];
    let mut start = 0;
    while start < order.len() {
        let mut end = start + 1;
        while end < order.len()
            && entries[order[start]].value == entries[order[end]].value
        {
            end += 1;
        }
        let first_rank = start + 1;
        let last_rank = end;
        let average = (first_rank + last_rank) as f64 / 2.0;
        for idx in &order[start..end] {
            ranks[*idx] = average;
        }
        start = end;
    }
    ranks
}

fn compute_rra_pvalue(ranks: &[f64], total_guides: usize) -> f64 {
    if ranks.is_empty() {
        return 1.0;
    }
    let denominator = total_guides as f64;
    let mut normalized: Vec<f64> = ranks
        .iter()
        .map(|rank| (rank / denominator).clamp(0.0, 1.0))
        .collect();
    normalized.sort_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));

    let mut min_prob = 1.0;
    for (i, value) in normalized.iter().enumerate() {
        let alpha = (i + 1) as f64;
        let beta_param = (total_guides - i) as f64;
        if let Ok(beta_dist) = Beta::new(alpha, beta_param.max(1.0)) {
            let cdf = beta_dist.cdf(*value);
            if cdf < min_prob {
                min_prob = cdf;
            }
        }
    }
    min_prob
}

fn weighted_mean(values: &[f64], weights: &[f64]) -> f64 {
    let mut total_weight = 0.0;
    let mut accumulator = 0.0;
    for (value, weight) in values.iter().zip(weights.iter()) {
        if weight.is_finite() && *weight > 0.0 {
            total_weight += weight;
            accumulator += value * weight;
        }
    }
    if total_weight > 0.0 {
        accumulator / total_weight
    } else if !values.is_empty() {
        values.iter().copied().sum::<f64>() / values.len() as f64
    } else {
        f64::NAN
    }
}

fn median(values: &mut [f64]) -> f64 {
    if values.is_empty() {
        return f64::NAN;
    }
    values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));
    let mid = values.len() / 2;
    if values.len() % 2 == 0 {
        (values[mid - 1] + values[mid]) / 2.0
    } else {
        values[mid]
    }
}

fn variance(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mean = values.iter().copied().sum::<f64>() / values.len() as f64;
    values
        .iter()
        .map(|value| {
            let diff = value - mean;
            diff * diff
        })
        .sum::<f64>()
        / values.len() as f64
}

fn benjamini_hochberg(pvalues: &[f64]) -> Vec<f64> {
    let mut pairs: Vec<(usize, f64)> = pvalues
        .iter()
        .cloned()
        .enumerate()
        .collect();
    pairs.sort_by(|(_, left), (_, right)| {
        match (left.is_nan(), right.is_nan()) {
            (true, true) => Ordering::Equal,
            (true, false) => Ordering::Greater,
            (false, true) => Ordering::Less,
            (false, false) => left
                .partial_cmp(right)
                .unwrap_or(Ordering::Equal),
        }
    });

    let n = pvalues.len();
    let mut adjusted = vec![1.0; n];
    let mut cumulative: f64 = 1.0;
    for (i, (idx, pvalue)) in pairs.iter().enumerate().rev() {
        let rank = (i + 1) as f64;
        let scaled = (pvalue * n as f64) / rank;
        cumulative = cumulative.min(scaled);
        adjusted[*idx] = cumulative.clamp(0.0, 1.0);
    }
    adjusted
}

#[pyfunction]
#[pyo3(signature = (log2fc, genes, weights=None, p_values=None, min_guides=2, higher_is_better=true))]
fn run_rra_native(
    py: Python<'_>,
    log2fc: PyReadonlyArray1<'_, f64>,
    genes: Vec<String>,
    weights: Option<PyReadonlyArray1<'_, f64>>,
    p_values: Option<PyReadonlyArray1<'_, f64>>,
    min_guides: usize,
    higher_is_better: bool,
) -> PyResult<PyObject> {
    let log2fc = log2fc.as_array();
    let n = log2fc.len();
    if n == 0 {
        return Err(PyValueError::new_err("log2fc array is empty"));
    }
    if genes.len() != n {
        return Err(PyValueError::new_err(
            "genes length must match log2fc values",
        ));
    }

    let weights_vec = match weights {
        Some(w) => {
            let arr = w.as_array();
            if arr.len() != n {
                return Err(PyValueError::new_err(
                    "weights length must match log2fc values",
                ));
            }
            arr.to_vec()
        }
        None => vec![1.0; n],
    };

    let _pvalues_vec = match p_values {
        Some(pvals) => {
            let arr = pvals.as_array();
            if arr.len() != n {
                return Err(PyValueError::new_err(
                    "p_values length must match log2fc values",
                ));
            }
            Some(arr.to_vec())
        }
        None => None,
    };

    let mut entries: Vec<GuideEntry> = Vec::with_capacity(n);
    for idx in 0..n {
        let value = log2fc[idx];
        if !value.is_finite() {
            continue;
        }
        let gene = genes[idx].trim();
        if gene.is_empty() {
            continue;
        }
        let weight = weights_vec[idx];
        entries.push(GuideEntry {
            gene: gene.to_string(),
            value,
            weight,
        });
    }

    if entries.is_empty() {
        return Err(PyValueError::new_err(
            "No valid guides available for RRA computation",
        ));
    }

    let ranks = compute_ranks(&entries, higher_is_better);

    let mut grouped: IndexMap<String, Vec<usize>> = IndexMap::new();
    for (idx, entry) in entries.iter().enumerate() {
        grouped.entry(entry.gene.clone()).or_default().push(idx);
    }

    let total_guides = entries.len();
    let mut records: Vec<RraRecord> = Vec::new();

    for (gene, indices) in grouped {
        if indices.len() < min_guides {
            continue;
        }

        let mut gene_values: Vec<f64> = Vec::with_capacity(indices.len());
        let mut gene_weights: Vec<f64> = Vec::with_capacity(indices.len());
        let mut gene_ranks: Vec<f64> = Vec::with_capacity(indices.len());

        for idx in &indices {
            gene_values.push(entries[*idx].value);
            gene_weights.push(entries[*idx].weight);
            gene_ranks.push(ranks[*idx]);
        }

        let p_value = compute_rra_pvalue(&gene_ranks, total_guides);
        let score = if p_value <= f64::MIN_POSITIVE {
            f64::INFINITY
        } else {
            -p_value.log10()
        };

        let mean = weighted_mean(&gene_values, &gene_weights);
        let mut median_values = gene_values.clone();
        let median_value = median(&mut median_values);
        let variance_value = variance(&gene_values);

        records.push(RraRecord {
            gene,
            score,
            p_value,
            fdr: 1.0,
            rank: 0,
            n_guides: indices.len(),
            mean_log2fc: mean,
            median_log2fc: median_value,
            var_log2fc: variance_value,
        });
    }

    if records.is_empty() {
        return Err(PyValueError::new_err(
            "No genes met the minimum guide requirement for RRA",
        ));
    }

    records.sort_by(|a, b| {
        match a
            .p_value
            .partial_cmp(&b.p_value)
        {
            Some(Ordering::Less) => Ordering::Less,
            Some(Ordering::Greater) => Ordering::Greater,
            Some(Ordering::Equal) | None => a
                .gene
                .cmp(&b.gene),
        }
    });

    let pvalues: Vec<f64> = records.iter().map(|record| record.p_value).collect();
    let fdr_values = benjamini_hochberg(&pvalues);
    for (idx, record) in records.iter_mut().enumerate() {
        record.fdr = fdr_values[idx];
        record.rank = idx + 1;
    }

    let py_results = PyList::empty(py);
    for record in &records {
        let row = PyDict::new(py);
        row.set_item("gene", &record.gene)?;
        row.set_item("score", record.score)?;
        row.set_item("p_value", record.p_value)?;
        row.set_item("fdr", record.fdr)?;
        row.set_item("rank", record.rank)?;
        row.set_item("n_guides", record.n_guides)?;
        row.set_item("mean_log2fc", record.mean_log2fc)?;
        row.set_item("median_log2fc", record.median_log2fc)?;
        row.set_item("var_log2fc", record.var_log2fc)?;
        py_results.append(row)?;
    }

    Ok(py_results.into())
}

#[pyfunction(name = "_backend_info")]
fn backend_info(py: Python<'_>) -> PyResult<PyObject> {
    let info = PyDict::new(py);
    info.set_item("name", "crispr_native_rust")?;
    info.set_item("version", env!("CARGO_PKG_VERSION"))?;
    info.set_item("simd_enabled", cfg!(feature = "simd"))?;
    info.set_item("rayon_enabled", cfg!(feature = "rayon"))?;
    info.set_item("build_profile", option_env!("PROFILE").unwrap_or("release"))?;
    Ok(info.into())
}

#[pymodule]
fn crispr_native_rust(py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(backend_info, m)?)?;
    m.add_function(wrap_pyfunction!(run_rra_native, m)?)?;
    Ok(())
}
