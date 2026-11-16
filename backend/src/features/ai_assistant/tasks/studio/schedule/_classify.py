"""The timeout the schedule's long model calls share."""

# Generous timeout plus a second attempt, the answers get long.
# A packet of 120 verdicts measured 171 s, a slow provider needs the rest.
_CLASSIFY_TIMEOUT_SECS = 600
