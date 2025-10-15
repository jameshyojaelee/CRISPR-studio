#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef CRISPR_NATIVE_HAS_OPENMP
#include <omp.h>
#endif

namespace py = pybind11;

namespace {

py::dict backend_info() {
    py::dict info;
    int openmp_threads = 1;
#ifdef CRISPR_NATIVE_HAS_OPENMP
    openmp_threads = omp_get_max_threads();
#endif
    info["name"] = "crispr_native";
    info["backend"] = "cpp";
    info["version"] = "0.1.0";
    info["compiler"] = PYBIND11_COMPILER_TYPE;
    info["openmp_threads"] = openmp_threads;
    info["has_openmp"] = openmp_threads > 1;
    return info;
}

double log_combination(std::uint32_t n, std::uint32_t k) {
    if (k > n) {
        return -std::numeric_limits<double>::infinity();
    }
    return std::lgamma(static_cast<double>(n) + 1.0) -
           std::lgamma(static_cast<double>(k) + 1.0) -
           std::lgamma(static_cast<double>(n - k) + 1.0);
}

double hypergeometric_sf(
    std::uint32_t universe_size,
    std::uint32_t set_size,
    std::uint32_t sample_size,
    std::uint32_t overlap
) {
    if (overlap > set_size || overlap > sample_size) {
        overlap = std::min(set_size, sample_size);
    }
    const std::uint32_t max_success = std::min(set_size, sample_size);
    if (overlap > max_success) {
        return 0.0;
    }

    const double log_denom = log_combination(universe_size, sample_size);
    double max_log = -std::numeric_limits<double>::infinity();
    std::vector<double> logs;
    logs.reserve(max_success - overlap + 1);

    for (std::uint32_t k = overlap; k <= max_success; ++k) {
        const double log_term =
            log_combination(set_size, k) +
            log_combination(universe_size - set_size, sample_size - k) -
            log_denom;
        logs.push_back(log_term);
        if (log_term > max_log) {
            max_log = log_term;
        }
    }

    double sum = 0.0;
    for (double log_term : logs) {
        sum += std::exp(log_term - max_log);
    }

    const double p_value = std::exp(max_log) * sum;
    return std::min(1.0, p_value);
}

py::list hypergeometric_enrichment(
    const std::vector<std::vector<std::uint32_t>>& gene_sets,
    const std::vector<std::string>& gene_names,
    const std::vector<std::uint32_t>& hit_indices,
    std::uint32_t universe_size
) {
    if (gene_sets.size() != gene_names.size()) {
        throw std::invalid_argument("gene_sets and gene_names must be the same length");
    }
    if (universe_size == 0) {
        throw std::invalid_argument("universe_size must be greater than zero");
    }

    std::vector<std::uint8_t> hit_lookup(universe_size, 0);
    for (std::uint32_t index : hit_indices) {
        if (index >= universe_size) {
            throw std::out_of_range("hit index exceeds universe size");
        }
        hit_lookup[index] = 1;
    }

    const std::uint32_t sample_size = static_cast<std::uint32_t>(hit_indices.size());
    py::list results;

    for (std::size_t idx = 0; idx < gene_sets.size(); ++idx) {
        const auto& gene_set = gene_sets[idx];
        const std::uint32_t set_size = static_cast<std::uint32_t>(gene_set.size());
        std::uint32_t overlap = 0;
        for (std::uint32_t gene_index : gene_set) {
            if (gene_index >= universe_size) {
                throw std::out_of_range("gene index exceeds universe size");
            }
            overlap += hit_lookup[gene_index];
        }

        const double p_value = hypergeometric_sf(universe_size, set_size, sample_size, overlap);
        const double expected = (static_cast<double>(set_size) * static_cast<double>(sample_size)) /
                                static_cast<double>(universe_size);
        py::dict row;
        row["name"] = gene_names[idx];
        row["set_size"] = set_size;
        row["overlap"] = overlap;
        row["p_value"] = p_value;
        row["expected_hits"] = expected;
        results.append(row);
    }

    return results;
}

}  // namespace

PYBIND11_MODULE(crispr_native, m) {
    m.doc() = "CRISPR-studio C++ native extensions";
    m.def("_backend_info_cpp", &backend_info, "Return build and environment metadata for the C++ backend.");
    m.def(
        "_hypergeometric_enrichment",
        &hypergeometric_enrichment,
        py::arg("gene_sets"),
        py::arg("gene_names"),
        py::arg("hit_indices"),
        py::arg("universe_size"),
        "Compute hypergeometric enrichment probabilities for batches of gene sets.");
}
