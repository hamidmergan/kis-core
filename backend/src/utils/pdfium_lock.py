"""One pdfium call at a time per process, the library is not thread safe.

Two threads inside pdfium at once crash the whole process (double free), and with it
every page request that process was serving.
"""

import threading

PDFIUM_LOCK = threading.RLock()
