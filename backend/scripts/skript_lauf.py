"""Writes a podcast script for an existing job's sources and params, without touching the job."""
import json
import sys
import time

from src.features.podcast import store
from src.services import sources as quellen
from src.services import text_map as tm
from src.services import feature_router
from src.services.feature_provider_choices import binding_for
from src.tasks.podcast_tasks import _script as s

USER, JOB = 1, sys.argv[1]
ZIEL = sys.argv[2]
params = store.load_params(USER, JOB)
if len(sys.argv) > 3:
    params.length = sys.argv[3]
if len(sys.argv) > 4:
    params.language = sys.argv[4]
llm = feature_router.make_llm_client(binding_for("chat", params.llm_provider_id))
karte = tm.Karte(quellen.load_sources(USER, JOB))
g = s._grundlage(USER, JOB, karte, params, llm)
t = time.time()
zeilen = s._schreiben(llm, karte, g, params, "0" * 32, None)
json.dump({"sekunden": round(time.time() - t), "names": [p.name for p in params.persons],
           "lines": [{"speaker": z.speaker, "text": z.text} for z in zeilen]},
          open(ZIEL, "w"), ensure_ascii=False, indent=1)
print("fertig", len(zeilen), round(time.time() - t), "s")
