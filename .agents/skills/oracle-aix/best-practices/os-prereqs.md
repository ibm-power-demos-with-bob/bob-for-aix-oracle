# Oracle on AIX: OS Prerequisites, Installation and Patching

> **Read this file for:** certified AIX levels, required filesets, IOCP, `sys0`
> settings (`maxuproc`, `ncargs`), Oracle users, groups, capabilities and
> resource limits, environment variables, time synchronisation, the 19c
> base + RU installation, and the Oracle and AIX patching procedures.
> **Authoritative sources:** the Oracle Database / Grid Infrastructure
> installation guide for AIX for your release, the MOS certification matrix, and
> IBM Support note 6825029. **The installer's prerequisite checks and `cluvfy`
> always win over this file.**

---

## 1. Certification and Levels

- Check the Oracle release against the AIX level in the **MOS certification
  matrix** (Certifications tab) before planning anything.
- Check IBM note 6825029 for the AIX APARs and iFixes recommended for Oracle at
  your TL/SP.

```bash
oslevel -s
instfix -i | grep -E 'ML|SP' | tail -3   # TL/SP filesets complete
lppchk -v                                # fileset consistency
```

---

## 2. Required Filesets (typical for 19c; confirm the exact list and levels in the install guide)

```bash
lslpp -l bos.adt.base bos.adt.lib bos.adt.libm bos.perf.libperfstat \
         bos.perf.perfstat bos.perf.proctools xlC.rte xlC.aix61.rte \
         rsct.basic.rte rsct.compat.clients.rte 2>&1 | grep -E "not installed|COMMITTED|APPLIED"
```

Install anything missing from the AIX base media or an lpp_source with
`installp -agXYd <dir> <filesets>` (preview first with `-p`).

---

## 3. I/O Completion Ports (IOCP) and AIO

Oracle on AIX needs the IOCP device to be **Available**:

```bash
lsdev -Cc iocp                           # expect: iocp0 Available
lsattr -El iocp0 -a autoconfig
chdev -l iocp0 -a autoconfig=available -P   # if Defined; it becomes Available after the next reboot (or: mkdev -l iocp0)
```

AIO loads on demand on AIX 6.1 and later. Tuning is in `io-storage.md` §3.

---

## 4. Users, Groups, Capabilities, Limits

```bash
# Groups and users (role separation; adapt the GIDs/UIDs to your standard and keep them identical on all RAC nodes)
mkgroup -A id=54321 oinstall
mkgroup -A id=54322 dba
mkgroup -A id=54327 asmdba
mkgroup -A id=54328 asmadmin
mkuser id=54321 pgrp=oinstall groups=oinstall,dba,asmdba home=/home/oracle shell=/usr/bin/ksh oracle
mkuser id=54331 pgrp=oinstall groups=oinstall,asmadmin,asmdba,dba home=/home/grid shell=/usr/bin/ksh grid

# Capabilities required by Oracle and Grid processes
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE oracle
chuser capabilities=CAP_NUMA_ATTACH,CAP_BYPASS_RAC_VMM,CAP_PROPAGATE grid
lsuser -a capabilities oracle grid
```

| Capability | Purpose |
|---|---|
| `CAP_NUMA_ATTACH` | Attach processes to resource sets (NUMA/SRAD affinity) |
| `CAP_BYPASS_RAC_VMM` | Bypass VMM resource-usage restrictions, for example to pin memory (used with `LOCK_SGA` and by Clusterware daemons) |
| `CAP_PROPAGATE` | Pass these capabilities on to child processes |

### Resource limits (`/etc/security/limits`)

```bash
lsuser -a fsize fsize_hard data data_hard stack stack_hard rss rss_hard \
          nofiles nofiles_hard cpu cpu_hard core oracle

# Typical Oracle settings: soft and hard limits unlimited (-1). Keep core files limited.
chuser fsize=-1 fsize_hard=-1 data=-1 data_hard=-1 stack=-1 stack_hard=-1 \
       rss=-1 rss_hard=-1 nofiles=-1 nofiles_hard=-1 cpu=-1 cpu_hard=-1 oracle
# repeat for grid
```

New limits apply at the user's next login, so restart the Oracle processes from a
new session.

---

## 5. `sys0` Settings

```bash
lsattr -El sys0 -a maxuproc -a ncargs
chdev -l sys0 -a maxuproc=16384     # >= 16384; on busy LPARs >= 128 + sum(PROCESSES) + PX servers
chdev -l sys0 -a ncargs=256         # >= 128 (in 4 KB blocks) for long command lines
```

Both changes take effect immediately and persist in the ODM.

---

## 6. Ephemeral Ports and Network Prerequisites

See `network-rac.md` §2 (ephemeral port range) and §5 (`/etc/netsvc.conf`).

---

## 7. Environment Variables

Verify that the variables are defined before any Oracle command: use the "Oracle
environment pre-flight check" in `SKILL.md`.

| Variable | Value | Notes |
|---|---|---|
| `ORACLE_BASE`, `ORACLE_HOME`, `ORACLE_SID` | Per installation (see `SKILL.md`) | Must be set and consistent with `/etc/oratab`. Never guess them |
| `PATH` | Includes `$ORACLE_HOME/bin` | `whence -p sqlplus` must resolve inside `$ORACLE_HOME` |
| `TNS_ADMIN` | Optional | If set, it must be a directory with the expected `tnsnames.ora`/`sqlnet.ora` |
| `LIBPATH` | `$ORACLE_HOME/lib:/usr/lib` | AIX uses `LIBPATH`, not `LD_LIBRARY_PATH` |
| `AIXTHREAD_SCOPE` | `S` | System-scope threads. Oracle recommends it on AIX |
| `AIX_TZCACHE` | `ON` | IBM ATG recommendation: caches time zone information (AIX 7.1+) |
| `ORACLE_SGA_PGSZ` | `16MB` only with pre-allocated 16 MB pages | See `memory.md` §5. Never set it to `64KB` while 16 MB pages are configured |
| `LDR_CNTRL` | Only for Oracle releases before 12.1 | See `memory.md` §1 |

For Clusterware or Restart-managed databases, set the environment with
`srvctl setenv`, because shell profile values are ignored by `srvctl start`:

```bash
srvctl setenv database -db <db> -envs "AIXTHREAD_SCOPE=S,AIX_TZCACHE=ON"
srvctl getenv database -db <db>
```

---

## 8. Time Synchronisation (RAC)

RAC needs NTP in **slewing mode** (`-x`) so the clock never steps backwards.

```bash
chssys -s xntpd -a "-x"                   # make SRC start xntpd with -x
# make sure /etc/rc.tcpip starts xntpd at boot (uncomment the start line)
stopsrc -s xntpd; startsrc -s xntpd
ps -ef | grep "[x]ntpd"                   # must show -x
lssrc -ls xntpd                           # sync state and peer
```

---

## 9. Oracle 19c Installation: Base Release Plus RU in One Step

On AIX, 19c installs from the **19.3 base image**, and you should then run a
current RU. Apply the RU during installation with `-applyRU`:

1. **Prepare as root:**
   - Run `rootpre.sh` from the installation media or home **if the install guide
     for your release requires it on AIX**.
   - Then run `/usr/sbin/slibclean`.
2. **As the software owner:**
   - Unzip the 19.3 image into the new home.
   - Replace `$ORACLE_HOME/OPatch` with the **latest OPatch** (patch 6880880).
     Older OPatch versions fail with `-applyRU`.
3. **Install with the RU:**

```bash
# Grid Infrastructure home (as grid)
./gridSetup.sh -applyRU /stage/patches/<GI_RU_patch_number> \
  -silent -responseFile /stage/grid_install.rsp

# Database home (as oracle)
./runInstaller -applyRU /stage/patches/<DB_RU_patch_number> \
  -silent -responseFile /stage/db_install.rsp
```

4. Run the `root.sh` / `orainstRoot.sh` scripts when the installer asks for them.
   Then check the result with `opatch lspatches`.

**RU numbers:** Grid RUs and DB RUs have different patch numbers. Take them from
MOS ("Assistant: Download Reference for Oracle Database/GI Update, Revision, PSU,
SPU (CPU), Bundle Patches, Patchsets and Base Releases"). The source recommended
19.22 in May 2024. Always use the current RU.

---

## 10. Patching an Existing Oracle Home

0. **Verify the environment** for the home being patched (`ORACLE_HOME`, `PATH`,
   `LIBPATH`, `ORACLE_SID`) with the "Oracle environment pre-flight check" in
   `SKILL.md`. `opatch` and `datapatch` act on `$ORACLE_HOME`: a wrong value patches
   the wrong home.
1. **Back up:**
   - RMAN backup.
   - `tar` of the Oracle home and the inventory.
   - Note the current `opatch lspatches` output.
2. **Update OPatch** in each home and unzip the patch.
3. **Check for conflicts:**

```bash
: "${ORACLE_HOME:?ORACLE_HOME is not set}"
$ORACLE_HOME/OPatch/opatch prereq CheckConflictAgainstOHWithDetail -ph ./
$ORACLE_HOME/OPatch/opatch prereq CheckSystemSpace -ph ./
```

4. **Stop everything that runs from the home** (instances, listeners, agents).
   Then, as root, unload unused shared libraries:

```bash
/usr/sbin/slibclean
genld -l | grep -i "$ORACLE_HOME"     # should return nothing once the home is idle
```

5. **Apply the patch:**
   - Database home: `opatch apply` (as oracle).
   - Grid home: `opatchauto apply <patch_dir>` as root. This handles one node at
     a time in RAC.
6. **Post-patch:** start the database and run `$ORACLE_HOME/OPatch/datapatch
   -verbose` (all PDBs open). Check `dba_registry_sqlpatch`.
7. **Rollback path:** `opatch rollback -id <patch_id>` (or `opatchauto rollback`),
   then `datapatch -verbose`.
8. **Workarounds that need re-applying:**
   - Check `memory.md` §9 (the `ldedit -b shrsymtab` workaround on affected AIX
     7.2 levels). It must be re-applied after any relink.
   - Update the embedded JDK (`misc.md` §5) as part of the same cycle.

---

## 11. AIX Fixes for Oracle Hosts

```bash
emgr -l                    # installed iFixes: make sure the iFixes IBM recommends for Oracle are present
instfix -ik <APAR>         # is a specific APAR fixed?
install_all_updates -d /mnt/<tl_sp> -p -Y     # preview a TL/SP update
```

- Do AIX updates in a **separate change** from Oracle patching. Use an
  `alt_disk_copy` clone or a `mksysb` as the fallback.
- Leave the filesets APPLIED until the update is validated.
- After an AIX TL update, run `/usr/sbin/slibclean` and, if the install guide
  requires it for your release, relink the Oracle binaries (`relink all` as the
  owner, with the home stopped).

---

## References

- Oracle Database installation guide for AIX (19c): https://docs.oracle.com/en/database/oracle/oracle-database/19/axdbi/
- Oracle Grid Infrastructure installation guide for AIX (19c): https://docs.oracle.com/en/database/oracle/oracle-database/19/cwaix/
- IBM: AIX with Oracle Database on IBM Power, performance and stability: https://www.ibm.com/support/pages/node/6825029
- IBM: Oracle Database 19c and RAC on AIX, tips and considerations: https://www.ibm.com/support/pages/node/6355761
- MOS: certification matrix (Certifications tab); OPatch: patch 6880880
