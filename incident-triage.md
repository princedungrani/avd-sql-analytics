# Incident Triage Runbook

1. Query MySQL for orphaned sessions (>15m no heartbeat).  
2. Log off stale sessions; confirm FSLogix container remounts.  
3. If repeated failures: reassign to healthy host; verify storage.  
4. Reimage out-of-date hosts; confirm agent/image versions.  
5. Document RCA; update automation/alerts.
