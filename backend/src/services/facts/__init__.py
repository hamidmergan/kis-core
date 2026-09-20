"""The format neutral half of a map reduce run.

Reads every source into facts, numbers them into one pool, and keeps them across
attempts. What a tool then builds out of that pool is the tool's own business.
"""

from src.services.facts.mapping import (
    Pacing,
    RateLimited,
    ReadSource,
    RunInterrupted,
    map_sources,
    overloaded,
)
from src.services.facts.pool import (
    Fact,
    build_pool,
    fact_line,
    facts_block,
    facts_for,
    parse_facts,
    pool_block,
    salvage_facts,
    source_names,
    unique_statements,
)
from src.services.facts.store import (
    FACTS_FILE,
    FactStore,
    JobFactStore,
    keepalive,
    parse_job_json,
    read_job_text,
    write_job_text,
)

__all__ = [
    "FACTS_FILE", "Fact", "FactStore", "JobFactStore", "Pacing", "RateLimited",
    "ReadSource", "RunInterrupted", "build_pool", "fact_line", "facts_block", "facts_for",
    "keepalive", "map_sources", "overloaded", "parse_facts", "parse_job_json",
    "pool_block", "read_job_text", "salvage_facts", "source_names", "unique_statements",
    "write_job_text",
]
