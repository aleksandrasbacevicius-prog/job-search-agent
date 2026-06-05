from langgraph.graph import END, StateGraph

from agents.job_board_scanner import run_job_board_scanner
from agents.scanner import ScannerState, load_sources, run_scanner
from utils.profile import load_profile
from utils.settings import load_settings


def build_pipeline():
    graph = StateGraph(ScannerState)
    graph.add_node("url_scanner", run_scanner)
    graph.add_node("job_board_scanner", run_job_board_scanner)
    graph.set_entry_point("url_scanner")
    graph.add_edge("url_scanner", "job_board_scanner")
    graph.add_edge("job_board_scanner", END)
    return graph.compile()


def run_scan() -> dict:
    pipeline = build_pipeline()
    return pipeline.invoke(
        {
            "sources": load_sources(),
            "profile": load_profile(),
            "new_postings": [],
            "scan_errors": [],
            "scan_summary": {},
        }
    )
