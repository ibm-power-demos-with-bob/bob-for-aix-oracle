# Agent Evaluations for AIX and Oracle Skills

This directory contains automated evaluation suites to verify the accuracy, portability, and practical utility of the `aix`, `ansible-aix`, and `oracle-aix` skills on IBM Power Systems (including live IBM Cloud PowerVS LPARs such as `aix-oracle01`).

## Test Suite Structure

- `test_evals.py`: Automated pytest/Python test suite evaluating:
  1. **AIX System Administration & Diagnostics**: Correct command generation (`lparstat`, `vmstat`, `svmon`, `errpt`, `vmo`, `ioo`, `no`, `schedo`, `lsvg`, `lsmpio`).
  2. **Ansible AIX Playbook Standards**: `ibm.power_aix` modules, YAML syntax, `ansible-lint` compliance, and lack of Linux-isms (`systemctl`, `date -d`, `useradd`, etc.).
  3. **Oracle on AIX / Power Systems Layout**:
     - Pre-flight environment check enforcement (`ORACLE_HOME`, `ORACLE_SID`, `PATH`, `LIBPATH`, etc.).
     - OS user verification defaults (`oracle` for DB, `grid` for ASM/RAC, prompt if missing).
     - Standardized shell execution (bash compatibility with AIX native ksh93 support).
     - Storage layout best practices: minimum 8 data LUNs, 8 redo LUNs, 2-4 backup LUNs, bflash/Tier 1 Flash tiering, `queue_depth` (64-256), `AU_SIZE=4M/8M`.
     - CPU & memory sizing: Power10 SMT-8 entitlement, large pages (`ORACLE_SGA_PGSZ=16m`, `vmo_lgpg_regions`), memory affinity (`AIXTHREAD_SCOPE=S`).
  4. **PowerVS Live Compatibility**: Scenario checks tailored for IBM Cloud PowerVS instance `aix-oracle01` (Power10, AIX 7.3 TL04, General-Flash-96 storage pool).

## Running Evaluations

To run the complete evaluation suite:

```bash
python evals/run_evals.py
```
