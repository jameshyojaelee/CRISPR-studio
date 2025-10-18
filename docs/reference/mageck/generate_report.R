#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 1 || length(args) > 2) {
  cat("Usage: Rscript generate_report.R <comparison_name> [fdrcutoff]\\n")
  quit(status = 1)
}

comparison_name <- args[[1]]
fdrcutoff <- if (length(args) == 2) as.numeric(args[[2]]) else 0.05

get_script_path <- function() {
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg_prefix <- "--file="
  file_arg <- cmd_args[grepl(file_arg_prefix, cmd_args)]
  if (length(file_arg) > 0) {
    return(normalizePath(sub(file_arg_prefix, "", file_arg)))
  }
  if (!is.null(sys.frames()[[1]]$ofile)) {
    return(normalizePath(sys.frames()[[1]]$ofile))
  }
  stop("Unable to determine script path; run via Rscript.")
}

script_dir <- dirname(get_script_path())
template_path <- file.path(script_dir, "report_template.Rmd")
output_path <- file.path(getwd(), sprintf("%s_report.html", comparison_name))

suppressPackageStartupMessages({
  library(rmarkdown)
})

render(
  input = template_path,
  output_file = output_path,
  params = list(
    comparison_name = comparison_name,
    fdrcutoff = fdrcutoff
  ),
  envir = new.env()
)

cat(sprintf("Generated MAGeCK notebook: %s\\n", output_path))
