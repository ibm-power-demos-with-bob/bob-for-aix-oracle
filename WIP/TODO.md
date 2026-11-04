1. Check that the Oracle environment variables are defined.
2. Use the `oracle` and `grid` users by default; ask for the user name if not present.
3. Does IBM Bob use bash or ksh to run commands? Standardize execution on bash.
4. Install best practices to take into account:
   - 8 volumes for data
   - 8 volumes for redo logs
   - 2 or 4 volumes for backups
   - flash (bflash) for better performance
5. Generate evals and test yourself that these skills are useful on the AIX Power machine on IBM Cloud, visible via the ibmcloud CLI.
