"""
Wrapper for report generation to maintain backward compatibility.
The actual implementation resides in app.reports.monthly_report.
"""
from app.reports.monthly_report import generate_monthly_report_excel

__all__ = ["generate_monthly_report_excel"]
