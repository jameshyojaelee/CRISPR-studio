"""Custom exceptions for CRISPR-studio data handling."""

from __future__ import annotations


class DataContractError(Exception):
    """Raised when input files violate the documented data contract."""

    def __init__(self, message: str):
        super().__init__(message)
