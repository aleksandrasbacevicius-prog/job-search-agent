from langgraph.graph import END, StateGraph

from agents.scanner import ScannerState, load_sources, run_scanner
from utils.profile import load_profile


def build_pipeline():
    graph = StateGraph(ScannerState)
    graph.add_node("scanner", run_scanner)
    graph.set_entry_point("scanner")
    graph.add_edge("scanner", END)
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
