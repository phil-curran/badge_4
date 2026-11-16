"""Build Badge 4 (Data Lake Workshop, DLKW) lesson notebooks for Snowflake Workspaces.

Usage: python3 build_badge4_notebooks.py
Output: ../notebooks/badge4_dlkw/  (10 lesson notebooks, dora/account_setup, dora/dora_setup, dora/dora_tests, data/)

Course code is read verbatim from the Rise export. In lesson notebooks only role and warehouse names are swapped:
    ACCOUNTADMIN -> {{ADMIN_ROLE}}     SYSADMIN -> {{SYSADMIN_ROLE}}     COMPUTE_WH -> {{WAREHOUSE}}
Code the course shows only in screenshots is transcribed and labelled. DORA code is never altered.
"""
import base64, html, json, os, re, shutil, uuid, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSE = os.path.join(ROOT, "badges", "badge-4-data-lake-workshop-raw")
ASSETS = os.path.join(COURSE, "assets")
OUT = os.path.join(ROOT, "notebooks", "badge4_dlkw")

ADMIN_ROLE, SYSADMIN_ROLE, WAREHOUSE = "BADGE4_DLKW_ADMIN", "BADGE4_DLKW_ROLE", "BADGE4_DLKW_WH"
DOWNLOADS = "@UTIL_DB.PUBLIC.BADGE4_DOWNLOADS"
SETUP_NB, DORA_SETUP_NB, DORA_NB = "dora/account_setup", "dora/dora_setup", "dora/dora_tests"

# course download -> list of files that end up in data/ (zips are unpacked, Mac metadata skipped)
ZIPS = {"sweatsuits.zip": "SWEATSUITS", "metadata.zip": "PRODUCT_METADATA", "geoJSON_files.zip": "TRAILS_GEOJSON"}


def zip_members(zname):
    z = zipfile.ZipFile(os.path.join(ASSETS, zname))
    return [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n and not os.path.basename(n).startswith(".")]


FILES = {s: sorted(os.path.basename(n) for n in zip_members(z)) for z, s in ZIPS.items()}
FILES["TRAILS_PARQUET"] = ["cherry_creek_trail.parquet"]


def copy_files(stage_fq, key):
    names = ", ".join(f"'{n}'" for n in FILES[key])
    return f"copy files into @{stage_fq}\nfrom {DOWNLOADS}\nfiles = ({names});"


# ---------------------------------------------------------------- course code
_raw = open(os.path.join(COURSE, "runtime-data.js")).read()
_course = json.loads(base64.b64decode(re.search(r'__jsonp\("runtime-data.js","(.*)"\)', _raw, re.S).group(1)))["course"]
CODE = {}
for _l in _course["lessons"]:
    _codes = [html.unescape(x.get("code") or "").replace("\r\n", "\n").strip("\n")
              for it in _l.get("items") or [] if it.get("type") == "multimedia" and it.get("variant") == "code"
              for x in it["items"]]
    if _codes:
        CODE[re.sub(r"<[^>]+>", "", _l["title"]).strip()] = _codes


def code(page, i=0):
    hits = [k for k in CODE if page in k]
    assert len(hits) == 1, (page, hits)
    return CODE[hits[0]][i]


def isolate(sql):
    sql = re.sub(r"\bACCOUNTADMIN\b", "{{ADMIN_ROLE}}", sql, flags=re.I)
    sql = re.sub(r"\bSYSADMIN\b", "{{SYSADMIN_ROLE}}", sql, flags=re.I)
    return re.sub(r"\bCOMPUTE_WH\b", "{{WAREHOUSE}}", sql, flags=re.I)


def dora_local(sql):
    return re.sub(r"select\s+GRADER\(step, \(actual = expected\), actual, expected,\s*description\)\s+as\s+graded_results\s+from",
                  "select step, actual, expected, (actual = expected) as passed, description from", sql, flags=re.I)


def protected(sql_text):
    """Run course code as given, but report instead of stopping if it errors (the course expects an error here)."""
    body = ("begin\n  execute immediate '" + sql_text.strip().rstrip(";").replace("'", "''") +
            "';\n  return 'ran without error';\nexception when other then\n  return 'Error (as the course predicts): ' || sqlerrm;\nend;")
    return "execute immediate '" + body.replace("'", "''") + "';"


def _id():
    return uuid.uuid4().hex[:8]


def md(text):
    return {"cell_type": "markdown", "id": _id(), "metadata": {}, "source": text.strip("\n")}


def sql(name, text):
    return {"cell_type": "code", "id": _id(), "execution_count": None, "outputs": [],
            "metadata": {"language": "sql", "name": name}, "source": f"%%sql -r {name}\n" + text.strip("\n")}


def py(name, text):
    return {"cell_type": "code", "id": _id(), "execution_count": None, "outputs": [],
            "metadata": {"language": "python", "name": name}, "source": text.strip("\n")}


def course(text):
    return md("> **Course:** " + text.strip().replace("\n", "\n> "))


def note(text):
    return md("> ⚠️ **Audit note:** " + text.strip().replace("\n", "\n> "))


def dora(step, what):
    return md(f"### 🤖 DORA check {step} goes here\nThe course has the learner run **{step}** ({what}) at this point.\n"
              f"It is in `{DORA_NB}.ipynb`, section **{step}**, as a local check plus the exact DORA code.")


def page(title):
    return md(f"## Page: {title}")


PREAMBLE_VARS = f"""# Isolation mapping (set once per notebook; SQL cells use these via {{{{...}}}})
ADMIN_ROLE    = "{ADMIN_ROLE}"   # stands in for the course's ACCOUNTADMIN
SYSADMIN_ROLE = "{SYSADMIN_ROLE}"    # stands in for the course's SYSADMIN
WAREHOUSE     = "{WAREHOUSE}"      # stands in for the course's COMPUTE_WH


def pdf(result):
    \"\"\"A SQL cell's result as pandas (runtime 2.6+ returns a Snowpark DataFrame).\"\"\"
    return result.to_pandas() if hasattr(result, "to_pandas") else result"""

PRODUCTS = "ZENAS_ATHLEISURE_DB.PRODUCTS"
TRAILS = "MELS_SMOOTHIE_CHALLENGE_DB.TRAILS"


def preamble(title, purpose, schema=None):
    ctx = "use role {{SYSADMIN_ROLE}};\nuse secondary roles none;\nuse warehouse {{WAREHOUSE}};\n"
    ctx += f"use schema {schema};\n" if schema else ""
    return [
        md(f"# Badge 4: Data Lake Workshop: {title}\n\n{purpose}\n\n"
           "**How to read this notebook**\n"
           "- Each `## Page:` heading is one page of the Rise lesson, in course order.\n"
           "- `> Course:` cells quote what the learner is told to do (text or screenshot steps).\n"
           "- Code cells run that task. Course code is verbatim except role/warehouse names, swapped for "
           f"`{ADMIN_ROLE}` (ACCOUNTADMIN), `{SYSADMIN_ROLE}` (SYSADMIN) and `{WAREHOUSE}` (COMPUTE_WH).\n"
           "- **SQL equivalent** replaces a UI-only step; **From screenshot** marks code the course shows only as an image; "
           "**Derived solution** marks challenge answers the course does not give.\n"
           f"- DORA checks are not run here; see `{DORA_NB}.ipynb`.\n"
           f"- Files the course has learners download are on `{DOWNLOADS}`, standing in for the learner's Downloads folder.\n\n"
           f"Prerequisite: run `{SETUP_NB}.ipynb` once."),
        py("isolation_vars", PREAMBLE_VARS),
        sql("session_context", ctx + "select current_role(), current_warehouse(), current_database(), current_schema();"),
    ]


def story(*titles):
    return md("Story / reading / knowledge-check pages, nothing to run: " + "; ".join(titles) + ".")


NB = {}

# ---------------------------------------------------------------- setup
NB[SETUP_NB] = [
    md("# Badge 4: Setup (run once, as ACCOUNTADMIN)\n\nCreates the isolated environment the lesson notebooks run in:\n\n"
       "| Course object | Isolated stand-in | Notes |\n|---|---|---|\n"
       f"| ACCOUNTADMIN role | `{ADMIN_ROLE}` | holds the account privileges the course uses as ACCOUNTADMIN |\n"
       f"| SYSADMIN role | `{SYSADMIN_ROLE}` | granted to `{ADMIN_ROLE}`, mirroring SYSADMIN under ACCOUNTADMIN |\n"
       f"| COMPUTE_WH | `{WAREHOUSE}` | X-Small, auto-suspend, owned by `{SYSADMIN_ROLE}` (Lesson 1 checklist) |\n"
       "| UTIL_DB | `UTIL_DB` | shared across badges; owned by SYSADMIN (Lesson 1 checklist) |\n"
       f"| learner's Downloads folder | `{DOWNLOADS}` | holds the files the course has learners download and unzip |\n\n"
       "Account-level steps (external volume, Marketplace listing, Iceberg database) run as the real ACCOUNTADMIN in the lesson notebooks and are labelled there. "
       "Object names (ZENAS_ATHLEISURE_DB, MELS_SMOOTHIE_CHALLENGE_DB, OPENSTREETMAP_DENVER, MY_ICEBERG_DB, ...) are the course's."),
    py("isolation_vars", PREAMBLE_VARS),
    md("## Check for name collisions\nCourse database names are account-wide."),
    sql("existing_course_objects", "use role accountadmin;\nshow databases like 'ZENAS_ATHLEISURE_DB';\nshow databases like 'MELS_SMOOTHIE_CHALLENGE_DB';\n"
        "show databases like 'OPENSTREETMAP_DENVER';\nshow databases like 'MY_ICEBERG_DB';\nshow external volumes like 'ICEBERG_EXTERNAL_VOLUME';"),
    md("## Roles and grants"),
    sql("create_roles", """use role accountadmin;
create role if not exists {{ADMIN_ROLE}} comment = 'Badge 4 stand-in for ACCOUNTADMIN';
create role if not exists {{SYSADMIN_ROLE}} comment = 'Badge 4 stand-in for SYSADMIN';
grant role {{SYSADMIN_ROLE}} to role {{ADMIN_ROLE}};
grant role {{ADMIN_ROLE}} to role sysadmin;
set badge_user = current_user();
grant role {{ADMIN_ROLE}} to user identifier($badge_user);
grant role {{SYSADMIN_ROLE}} to user identifier($badge_user);
-- SYSADMIN creates ZENAS_ATHLEISURE_DB and MELS_SMOOTHIE_CHALLENGE_DB (Lessons 2, 5)
grant create database on account to role {{SYSADMIN_ROLE}};
-- external tables auto-refresh and materialized views (Lesson 9)
grant create integration on account to role {{ADMIN_ROLE}};
-- ACCOUNTADMIN can read SNOWFLAKE.ACCOUNT_USAGE
grant imported privileges on database snowflake to role {{ADMIN_ROLE}};"""),
    md("## Warehouse (stands in for COMPUTE_WH; the Lesson 1 checklist says SYSADMIN owns it)"),
    sql("create_warehouse", """use role accountadmin;
create warehouse if not exists {{WAREHOUSE}}
  warehouse_size = xsmall auto_suspend = 60 auto_resume = true initially_suspended = true
  comment = 'Badge 4 stand-in for COMPUTE_WH';
grant ownership on warehouse {{WAREHOUSE}} to role {{SYSADMIN_ROLE}} copy current grants;"""),
    md("## UTIL_DB (shared across badges; home of the DORA GRADER)"),
    sql("util_db_grants", """use role accountadmin;
create database if not exists UTIL_DB comment = 'Shared utility database for badge course audits (DORA grader, course stages)';
grant ownership on database UTIL_DB to role sysadmin copy current grants;
grant ownership on schema UTIL_DB.PUBLIC to role sysadmin copy current grants;
grant usage on database UTIL_DB to role {{ADMIN_ROLE}};
grant usage on database UTIL_DB to role {{SYSADMIN_ROLE}};
grant usage, create stage, create workspace, create table on schema UTIL_DB.PUBLIC to role {{ADMIN_ROLE}};
grant usage, create table on schema UTIL_DB.PUBLIC to role {{SYSADMIN_ROLE}};"""),
    md("## Course data files (the learner's Downloads folder)\n"
       "The course has learners download `sweatsuits.zip`, `metadata.zip`, `geoJSON_files.zip` and `cherry_creek_trail.parquet`, unzip them and upload the files to stages. "
       "The unzipped files are in `data/` beside these notebooks; upload them once:\n\n"
       f"```\nsnow sql -q \"use role {ADMIN_ROLE}; put 'file://<path>/data/*' {DOWNLOADS} auto_compress=false overwrite=true\"\n```"),
    sql("create_downloads_stage", f"""use role {{{{ADMIN_ROLE}}}};
create stage if not exists {DOWNLOADS[1:]}
  comment = 'Badge 4: stands in for the learner''s local Downloads folder'
  directory = (enable = true)
  encryption = (type = 'SNOWFLAKE_SSE');
grant read on stage {DOWNLOADS[1:]} to role {{{{SYSADMIN_ROLE}}}};
alter stage {DOWNLOADS[1:]} refresh;
list {DOWNLOADS};"""),
    py("downloads_check", f"""expected = {sorted(n for v in FILES.values() for n in v)!r}
found = sorted(n.split('/')[-1] for n in pdf(create_downloads_stage)['name'])
print('Missing course files:', sorted(set(expected) - set(found)) or 'none')"""),
    md("## Teardown (commented out)\nRemoves everything Badge 4 creates."),
    sql("teardown", """-- use role accountadmin;
-- drop database if exists ZENAS_ATHLEISURE_DB;
-- drop database if exists MELS_SMOOTHIE_CHALLENGE_DB;
-- drop database if exists MY_ICEBERG_DB;
-- drop database if exists OPENSTREETMAP_DENVER;
-- drop external volume if exists ICEBERG_EXTERNAL_VOLUME;
-- drop table if exists UTIL_DB.PUBLIC.MY_DATA_TYPES;
-- drop stage if exists UTIL_DB.PUBLIC.BADGE4_DOWNLOADS;
-- drop warehouse if exists {{WAREHOUSE}};
-- drop role if exists {{SYSADMIN_ROLE}};
-- drop role if exists {{ADMIN_ROLE}};
select 'teardown is commented out' as status;"""),
]

NB[DORA_SETUP_NB] = [
    md("# Badge 4: DORA setup (course Lesson 1, 🎭 Set Up DORA!)\n\n"
       "⚠️ The cells create the API integration and the GRADER function that call Snowflake Education's external grading service. They are shared with the "
       "other badges; if another badge's DORA setup already ran, these cells recreate the same objects.\n\n"
       "Code is exactly as the course gives it, with the course's ACCOUNTADMIN."),
    md("### 1. Run the API Integration Script"),
    sql("dora_api_integration", code("Set Up DORA", 0)),
    md("### 2. Set up the Grader Function"),
    sql("dora_grader_function", code("Set Up DORA", 1)),
    md("### 3. Test the connection"),
    note("The course's step 3 code block is identical to step 2 (it recreates the GRADER function again). Unlike other badges, this course has no `DORA_IS_WORKING` test."),
    sql("dora_test_connection", code("Set Up DORA", 2)),
]

# ---------------------------------------------------------------- lesson 1
NB["lesson_01_getting_set_up"] = preamble("Lesson 1: Getting Set Up", f"Trial account checklist. DORA setup is in `{DORA_SETUP_NB}.ipynb`.") + [
    page("🎭 Meet Zena!"), md("Video and quiz only; nothing to run."),
    page("🧭 Set Up Your Trial Account"),
    course("Pre-requisites: Badge 1 (DWW) and Badge 2 (CMCW). Sign up for a trial on AWS US West (Oregon) (required: Lesson 9 sets up an Iceberg table). Activate the account."),
    sql("account_details", "select current_organization_name() as org, current_account_name() as account, current_account() as locator,\n"
        "       current_region() as region, current_user() as user_name;"),
    note("The course says the account **must** be AWS US West (Oregon). This account's region is shown above; Lesson 9 (Iceberg) depends on it."),
    page("📓 UI Changed? Of Course It Has!"), md("Reading and quiz only."),
    page("🎭 Set Up DORA!"), md(f"### 🤖 DORA setup goes here\nThe API integration and GRADER function are in `{DORA_SETUP_NB}.ipynb`."),
    page("💬 Tell Us About Your Snowflake Trial Account"),
    course("Create a new DLKW link row in the YSA App (https://ysa.snowflakeuniversity.com). Outside Snowflake; nothing to run."),
]

# ---------------------------------------------------------------- lesson 2
NB["lesson_02_data_structures_and_stages"] = preamble("Lesson 2: Reviewing Data Structuring & Stage Types", "Data types, ZENAS_ATHLEISURE_DB and its two internal stages.") + [
    page("📓 Reviewing Data Types"),
    sql("my_data_types", code("Reviewing Data Types")),
    note("The course gives no role for this table; it is created in the shared UTIL_DB.PUBLIC as the SYSADMIN stand-in."),
    page("📓 Reviewing Data Structuring"), md("Reading only."),
    page("🎭 Rapid Prototyping for Proof of Concepts"), md("Video and quiz only."),
    page("📓 Cloud Folders for Staging and Storing Files"),
    course("🎯 Create a Database for Zena's Athleisure Idea: create ZENAS_ATHLEISURE_DB owned by SYSADMIN; drop the PUBLIC schema; create a schema called PRODUCTS (also owned by SYSADMIN)."),
    sql("create_zenas_db", "-- Derived solution\nuse role {{SYSADMIN_ROLE}};\ncreate database ZENAS_ATHLEISURE_DB;\ndrop schema ZENAS_ATHLEISURE_DB.PUBLIC;\n"
        "create schema ZENAS_ATHLEISURE_DB.PRODUCTS;\nuse warehouse {{WAREHOUSE}};\nuse schema ZENAS_ATHLEISURE_DB.PRODUCTS;"),
    course("🥋 Create an Internal Stage and Load the Sweatsuit Files Into It: download and unzip sweatsuits.zip. UI steps (DLKW_003-008): Catalog → ZENAS_ATHLEISURE_DB → PRODUCTS → Create → Stage → "
           "**Snowflake Managed**; Stage Name **sweatsuits**; Directory table **on**; Encryption **Server-side**; Create. Then **+ Files** and add the 10 unzipped PNG files."),
    sql("create_sweatsuits_stage", "-- SQL equivalent of the Create Stage dialog (DLKW_005): directory table on, server-side encryption\ncreate stage ZENAS_ATHLEISURE_DB.PRODUCTS.SWEATSUITS\n"
        "  directory = (enable = true)\n  encryption = (type = 'SNOWFLAKE_SSE');"),
    sql("load_sweatsuits", "-- SQL equivalent of **+ Files**: the unzipped files sit on the Downloads stand-in stage\n" + copy_files("ZENAS_ATHLEISURE_DB.PRODUCTS.SWEATSUITS", "SWEATSUITS")
        + "\nalter stage ZENAS_ATHLEISURE_DB.PRODUCTS.SWEATSUITS refresh;\nlist @ZENAS_ATHLEISURE_DB.PRODUCTS.SWEATSUITS;"),
    page("🎯 Create Another Stage on Your Own"),
    course("🎯 Create Another Internal Stage: in the PRODUCTS schema, owned by SYSADMIN, named PRODUCT_METADATA, **client-side encryption**. Load the files from metadata.zip (DLKW_002: 3 files). "
           "At the end you should have one database, one dropped and one created schema (2 schemas), and 2 stages."),
    sql("create_product_metadata_stage", "-- SQL equivalent of the Create Stage dialog (Snowflake Managed, client-side encryption). DLKW_009's icons show no directory table on this stage.\n"
        "create stage ZENAS_ATHLEISURE_DB.PRODUCTS.PRODUCT_METADATA\n  encryption = (type = 'SNOWFLAKE_FULL');"),
    sql("load_product_metadata", "-- SQL equivalent of **+ Files**\n" + copy_files("ZENAS_ATHLEISURE_DB.PRODUCTS.PRODUCT_METADATA", "PRODUCT_METADATA") + "\nlist @ZENAS_ATHLEISURE_DB.PRODUCTS.PRODUCT_METADATA;"),
    sql("lab_check", "show schemas in database ZENAS_ATHLEISURE_DB;\nshow stages in schema ZENAS_ATHLEISURE_DB.PRODUCTS;"),
    page("📓 Reviewing the Concept of a Stage in Snowflake"), md("Reading and quiz only."),
    page("🤖 DORA DLKW01"), dora("DLKW01", "the two Zena stages exist"),
    page("🏁 Summary & Next Steps"), md("Checklist only."),
]

# ---------------------------------------------------------------- lesson 3
CRLF = "replace($1,chr(13)||chr(10))"
NB["lesson_03_leaving_data_where_it_lands"] = preamble("Lesson 3: Leaving the Data Where it Lands", "File formats and views over the non-loaded metadata files.", PRODUCTS) + [
    page("🥋 Leaving Data Where It Lands!"),
    sql("list_default_ctx", code("Leaving Data Where It Lands", 0)),
    sql("list_fully_qualified", code("Leaving Data Where It Lands", 1)),
    sql("select_dollar_1", code("Leaving Data Where It Lands", 2)),
    page("🥋 Helping Snowflake Interpret Data Files"),
    sql("select_one_file", code("Helping Snowflake")),
    page("🥋 Querying with the Help of File Formats"),
    sql("zmd_file_format_1_create", code("Querying with the Help", 0)),
    sql("zmd_file_format_1_select", code("Querying with the Help", 1)),
    sql("zmd_file_format_2_create", re.split(r";\s*\n\s*\n", code("Querying with the Help", 2))[0] + ";"),
    sql("zmd_file_format_2_select", re.split(r";\s*\n\s*\n", code("Querying with the Help", 2))[1]),
    course("🥋 A Third Possibility? Replace the question marks with the real delimiters. The block below is the course's template, run as written (the `?` are placeholders)."),
    note("The course's template sets both delimiters to `?`, which Snowflake rejects (the same character cannot be both). It runs as given and reports the error; the next page gives the real delimiters."),
    sql("zmd_file_format_3_template", protected(re.split(r";\s*\n\s*\n", code("Querying with the Help", 3))[0] + ";")),
    page("🥋 A Solid File Format for the Product Coordination File"),
    sql("zmd_file_format_3", code("A Solid File Format")),
    sql("zmd_file_format_3_select", "-- DLKW_020: caret = row separator, equal sign = column separator\nselect $1, $2\nfrom @product_metadata/product_coordination_suggestions.txt\n(file_format => zmd_file_format_3);"),
    page("🎯 Repurpose File Format 1 for the Sweatsuit Sizes File"),
    course("🎯 Rewrite zmd_file_format_1 to parse sweatsuit_sizes.txt (DLKW_021, 022): `create or replace`, then run the select."),
    sql("zmd_file_format_1_sizes", "-- Derived solution: the sizes are separated by semicolons\ncreate or replace file format zmd_file_format_1\nRECORD_DELIMITER = ';';"),
    sql("sizes_select", code("Repurpose File Format 1")),
    page("🎯 Repurpose File Format 2 for the Sweatband Product Line File"),
    course("🎯 Rewrite zmd_file_format_2 to parse swt_product_line.txt: 3 columns and 10 rows (DLKW_023, 024). Then add TRIM_SPACE = TRUE and re-run the select (DLKW_025)."),
    sql("zmd_file_format_2_product_line", "-- Derived solution: records end with ';', fields are separated by '|'\ncreate or replace file format zmd_file_format_2\nFIELD_DELIMITER = '|'\nRECORD_DELIMITER = ';';"),
    sql("product_line_select", "select $1, $2, $3\nfrom @product_metadata/swt_product_line.txt\n(file_format => zmd_file_format_2);"),
    sql("zmd_file_format_2_trim", "-- Derived solution: the course's TRIM_SPACE property\ncreate or replace file format zmd_file_format_2\nFIELD_DELIMITER = '|'\nRECORD_DELIMITER = ';'\nTRIM_SPACE = TRUE;"),
    sql("product_line_select_trim", "select $1, $2, $3\nfrom @product_metadata/swt_product_line.txt\n(file_format => zmd_file_format_2);"),
    page("🥋 Make the Sweatsuit Sizes Data Look Great!"),
    course("🎯 Make Sure All 3 File Formats Have a Trim Space Property ([TRIM_SPACE = True])."),
    sql("trim_all_file_formats", "-- Derived solution\nalter file format zmd_file_format_1 set TRIM_SPACE = TRUE;\nalter file format zmd_file_format_2 set TRIM_SPACE = TRUE;\nalter file format zmd_file_format_3 set TRIM_SPACE = TRUE;"),
    course("🥋 Dealing with Unexpected Characters: REPLACE($1, chr(13)||chr(10)) removes CRLF (DLKW_027 shows the select)."),
    sql("sizes_without_crlf", "-- From screenshot DLKW_027\nselect REPLACE($1,chr(13)||chr(10)) as sizes_available\nfrom @product_metadata/sweatsuit_sizes.txt\n(file_format => zmd_file_format_1);"),
    page("🥋 Make the Sweatsuit Sizes Data Even Better!"),
    sql("sizes_nonempty", "-- From screenshot DLKW_028: nix the empty 19th row\nselect REPLACE($1,chr(13)||chr(10)) as sizes_available\nfrom @product_metadata/sweatsuit_sizes.txt\n(file_format => zmd_file_format_1)\nwhere sizes_available <> '';"),
    course("🥋 Convert Your Select to a View: add this line above your select."),
    sql("create_sweatsuit_sizes", code("Make the Sweatsuit Sizes Data Even Better") + "\nselect REPLACE($1,chr(13)||chr(10)) as sizes_available\nfrom @product_metadata/sweatsuit_sizes.txt\n(file_format => zmd_file_format_1)\nwhere sizes_available <> '';"),
    sql("check_sweatsuit_sizes", "select * from zenas_athleisure_db.products.sweatsuit_sizes;"),
    page("🎯 Make the Sweatband Product Line File Look Great!"),
    sql("create_sweatband_product_line", "-- Derived solution (column names from DLKW_030)\ncreate view zenas_athleisure_db.products.SWEATBAND_PRODUCT_LINE as\n"
        "select REPLACE($1,chr(13)||chr(10)) as product_code\n,REPLACE($2,chr(13)||chr(10)) as headband_description\n,REPLACE($3,chr(13)||chr(10)) as wristband_description\n"
        "from @product_metadata/swt_product_line.txt\n(file_format => zmd_file_format_2)\nwhere product_code <> '';"),
    page("🎯 Make the Product Coordination Data Look Great!"),
    sql("create_sweatband_coordination", "-- Derived solution (column names from DLKW_033)\ncreate view zenas_athleisure_db.products.SWEATBAND_COORDINATION as\n"
        "select REPLACE($1,chr(13)||chr(10)) as product_code\n,REPLACE($2,chr(13)||chr(10)) as has_matching_sweatsuit\n"
        "from @product_metadata/product_coordination_suggestions.txt\n(file_format => zmd_file_format_3)\nwhere product_code <> '';"),
    page("🤖 DORA DLKW02"), dora("DLKW02", "views have no CRLFs"),
    page("🏁 Summary & Next Steps"),
    sql("summary_1", code("Summary & Next Steps", 0) if False else "select product_code, has_matching_sweatsuit\nfrom zenas_athleisure_db.products.sweatband_coordination;"),
    sql("summary_2", "select product_code, headband_description, wristband_description\nfrom zenas_athleisure_db.products.sweatband_product_line;"),
    sql("summary_3", "select sizes_available\nfrom zenas_athleisure_db.products.sweatsuit_sizes;"),
    sql("summary_counts", "-- 10, 10 and 18 rows expected\nselect (select count(*) from zenas_athleisure_db.products.sweatband_coordination) as coordination_rows,\n"
        "       (select count(*) from zenas_athleisure_db.products.sweatband_product_line) as product_line_rows,\n       (select count(*) from zenas_athleisure_db.products.sweatsuit_sizes) as sizes_rows;"),
]

# ---------------------------------------------------------------- lesson 4
CATALOG_APP = "Zena's Amazing Athleisure Catalog"
APP_NAME = f'ZENAS_ATHLEISURE_DB.PRODUCTS."{CATALOG_APP}"'
APP_PATH = f'snow://streamlit/ZENAS_ATHLEISURE_DB.PRODUCTS."{CATALOG_APP}"/versions/live/streamlit_app.py'
APP_CODE = code("Build Zena's SiS Prototype App") + "\n"

NB["lesson_04_unstructured_data"] = preamble("Lesson 4: Working with Non-Loaded Unstructured Data", "Directory tables, joins, CATALOG and CATALOG_FOR_WEBSITE, and the optional Streamlit app.", PRODUCTS) + [
    page("📓 Non-Loaded Data is Easy!"),
    course("🎯 Run a LIST command on the SWEATSUITS stage you created."),
    sql("list_sweatsuits", "list @sweatsuits;"),
    page("📓 Unstructured Non-Loaded Data"),
    note("The course says this query gives an error message (DLKW_038). It runs as given and reports what happens."),
    sql("select_dollar_1_png", protected(code("Unstructured Non-Loaded Data"))),
    page("🥋 Querying Non-Loaded Unstructured Data"),
    sql("metadata_columns", code("Querying Non-Loaded Unstructured Data")),
    course("🎯 Write a Query That Returns Something More Like a List Command: GROUP BY the file name with MAX or COUNT (DLKW_040)."),
    sql("list_like_query", "-- Derived solution (columns from DLKW_040)\nselect metadata$filename, max(metadata$file_row_number) as number_of_rows\nfrom @sweatsuits\ngroup by metadata$filename;"),
    page("📓 File Formats? Nope, Directory Tables!"),
    sql("directory_table", code("File Formats? Nope")),
    page("📓 Do Functions Work on Directory Tables?"),
    sql("directory_functions", code("Do Functions Work on Directory Tables")),
    course("🎯 Nest 3 Functions into 1 Statement: a single column named PRODUCT_NAME (DLKW_049, 050)."),
    sql("nested_functions", "-- From screenshot DLKW_054 (the complete nested expression)\nselect INITCAP(REPLACE(REPLACE(relative_path,'_',' '), '.png')) as product_name\nfrom directory(@sweatsuits);"),
    page("🥋 Can you Join Directory Tables with Other Tables?"),
    sql("create_sweatsuits_table", code("Can you Join Directory Tables")),
    course("🎯 Can You Join These? (DLKW_053, 054)"),
    sql("join_directory_table", "-- From screenshot DLKW_054, blur filled in\nselect INITCAP(REPLACE(REPLACE(relative_path,'_',' '), '.png')) as product_name\n, *\nfrom directory(@sweatsuits) d\njoin sweatsuits s\non d.relative_path = s.file_name;"),
    page("🥋 3 Way Join - CROSS JOIN Included!"),
    course("🎯 Replace the * With a List of Columns: create a view named PRODUCT_LIST (DLKW_055: PRODUCT_NAME, FILE_NAME, COLOR_OR_STYLE, PRICE, FILE_URL)."),
    sql("create_product_list", "-- Derived solution (columns from DLKW_055)\ncreate view product_list as\nselect INITCAP(REPLACE(REPLACE(relative_path,'_',' '), '.png')) as product_name\n, s.file_name\n, s.color_or_style\n, s.price\n, d.file_url\n"
        "from directory(@sweatsuits) d\njoin sweatsuits s\non d.relative_path = s.file_name;"),
    sql("cross_join", code("3 Way Join")),
    course("🎯 Convert Your Select Statement to a View: CATALOG, in Zena's database and PRODUCTS schema, owned by SYSADMIN; it should return 180 rows."),
    sql("create_catalog", "-- Derived solution\ncreate view catalog as\nselect * \nfrom product_list p\ncross join sweatsuit_sizes;"),
    sql("catalog_rows", "select count(*) as catalog_rows from catalog;"),
    page("🤖 DORA DLKW03"), dora("DLKW03", "CATALOG view returns 180 rows"),
    page("🥋 Do WHAT You Can, WHERE You Can, HOW You Can"),
    sql("create_upsell_mapping", code("Do WHAT You Can")),
    page("🥋 Kludges Galore? Or Relentless Resourcefulness?"),
    sql("create_catalog_for_website", code("Kludges Galore")),
    page("🤖 DORA DLKW04"), dora("DLKW04", "CATALOG_FOR_WEBSITE upsell descriptions"),
    page("🖼️ Zena's Ready to Meet Up with Mel!"), md("Story only."),
    page("🥋 Build Zena's SiS Prototype App (OPTIONAL)"),
    course("UI steps (DLKW_062, 063): Projects → Streamlit → **+ Streamlit App**; App title **Zena's Amazing Athleisure Catalog**; app location **ZENAS_ATHLEISURE_DB / PRODUCTS**; warehouse **COMPUTE_WH**; Create. "
           "Delete ALL the sample code (DLKW_063) and paste the course's app code."),
    sql("create_streamlit_app", f"""-- SQL equivalent of the Create Streamlit App dialog (DLKW_062)
use role {{{{SYSADMIN_ROLE}}}};
create streamlit {APP_NAME}
  runtime_name = 'SYSTEM$WAREHOUSE_RUNTIME'
  query_warehouse = {{{{WAREHOUSE}}}}
  title = 'Zena''s Amazing Athleisure Catalog';
alter streamlit {APP_NAME} add live version from last;"""),
    py("edit_streamlit_app_code", f'''# SQL equivalent of pasting the app code into the Streamlit editor: written into the app's live version
import io
from snowflake.snowpark.context import get_active_session
session = get_active_session()
APP_CODE = {APP_CODE!r}
session.file.put_stream(io.BytesIO(APP_CODE.encode()), {APP_PATH!r}, auto_compress=False, overwrite=True)
print(APP_CODE)'''),
    note("Snowsight assigns the app's object identifier (DLKW_065 shows a generated stage name, UCY5D7...); here the identifier is the title. The stage-less app has no app stage, so the course's "
         "'Load copies of the image files into your app's stage' route is not available; the app's final code (DLKW_073) uses the pre-signed URL instead, which needs no app stage."),
    page("🥋 Work Out Image Displays (OPTIONAL)"),
    course("🥋 Load copies of the images into your app's stage (DLKW_065, 071); 📓 The Second Option: pre-signed URLs (DLKW_072, 073): the app code already uses `url = pd_prod_data['FILE_URL'].iloc[0]` and `st.image(image=url, ...)`."),
    sql("app_query_check", "-- Not a course cell: the query the app runs for the first colour, checking the pre-signed URL column\nselect color_or_style, price, size_list, upsell_product_desc, left(file_url, 60) as file_url_start\n"
        "from catalog_for_website order by color_or_style limit 3;"),
]

# ---------------------------------------------------------------- lesson 5
NB["lesson_05_concept_kickoff"] = preamble("Lesson 5: Mel's Concept Kickoff", "MELS_SMOOTHIE_CHALLENGE_DB, the trails stages and file formats.") + [
    page("🎭 Mel's Playing Catch up!"), md("Quiz only."),
    page("📓 Geography Refresher!"), md("Reading and quiz only."),
    page("📓 Denver, Colorado, USA"), md("Reading and quiz only."),
    page("🎭 Mel's GeoSpatial Crash Course"), course("Explore earth.google.com, google.com/maps, openstreetmap.org and the WKT Playground. Outside Snowflake; nothing to run."),
    page("🎯 Camilla's GeoSpatial Data (Part 1)"),
    course("🎯 Put Your Snowflake Skills to Work! Everything owned by SYSADMIN: create MELS_SMOOTHIE_CHALLENGE_DB; drop the PUBLIC schema; add schema TRAILS; add internal named stages TRAILS_GEOJSON and TRAILS_PARQUET "
           "(client-side encryption is fine) in the TRAILS schema (DLKW_075)."),
    sql("create_mels_db", "-- Derived solution\nuse role {{SYSADMIN_ROLE}};\ncreate database MELS_SMOOTHIE_CHALLENGE_DB;\ndrop schema MELS_SMOOTHIE_CHALLENGE_DB.PUBLIC;\n"
        "create schema MELS_SMOOTHIE_CHALLENGE_DB.TRAILS;\nuse warehouse {{WAREHOUSE}};\nuse schema MELS_SMOOTHIE_CHALLENGE_DB.TRAILS;"),
    sql("create_trails_stages", "-- Derived solution. DLKW_075's icons show both stages with a directory table.\ncreate stage TRAILS_GEOJSON\n  directory = (enable = true)\n  encryption = (type = 'SNOWFLAKE_FULL');\n"
        "create stage TRAILS_PARQUET\n  directory = (enable = true)\n  encryption = (type = 'SNOWFLAKE_FULL');"),
    course("🎯 Load Your New Stages: download cherry_creek_trail.parquet and geoJSON_files.zip; unzip the geoJSON files into the geoJSON stage; load the Parquet file into the Parquet stage."),
    sql("load_trails_geojson", "-- SQL equivalent of **+ Files**\n" + copy_files("MELS_SMOOTHIE_CHALLENGE_DB.TRAILS.TRAILS_GEOJSON", "TRAILS_GEOJSON")),
    sql("load_trails_parquet", "-- SQL equivalent of **+ Files**\n" + copy_files("MELS_SMOOTHIE_CHALLENGE_DB.TRAILS.TRAILS_PARQUET", "TRAILS_PARQUET")),
    sql("list_trails_stages", "list @trails_geojson;\nlist @trails_parquet;"),
    page("🎯 Camilla's GeoSpatial Data (Part 2)"),
    course("🥋 Create a Very Basic JSON File Format (DLKW_077, 078): **FF_JSON**, type JSON, in the TRAILS schema. 🎯 Create a Very Basic Parquet File Format: **FF_PARQUET**, type PARQUET, in the TRAILS schema, owned by SYSADMIN."),
    sql("create_ff_json", "-- From screenshot DLKW_078\ncreate file format FF_JSON\n    type = JSON;"),
    sql("create_ff_parquet", "-- Derived solution\ncreate file format FF_PARQUET\n    type = PARQUET;"),
    sql("query_geojson", "-- From screenshot DLKW_080\nselect *\nfrom @trails_geojson\n(file_format => ff_json);"),
    sql("query_parquet", "-- Derived solution: the query above pointed at the Parquet stage\nselect *\nfrom @trails_parquet\n(file_format => ff_parquet);"),
    page("🤖 DORA DLKW05"), dora("DLKW05", "4 stage and file format objects in Mel's database"),
]

# ---------------------------------------------------------------- lesson 6
NB["lesson_06_geospatial_views"] = preamble("Lesson 6: GeoSpatial Views", "CHERRY_CREEK_TRAIL and DENVER_AREA_TRAILS.", TRAILS) + [
    page("🥋 Querying the Parquet File"),
    course("Write a more sophisticated query to parse the data into columns (DLKW_086)."),
    sql("parquet_columns", "-- From screenshot DLKW_086, blur filled in\nselect\n  $1:sequence_1 as sequence_1,\n  $1:trail_name::varchar as trail_name,\n  $1:latitude as latitude,\n  $1:longitude as longitude,\n"
        "  $1:sequence_2 as sequence_2,\n  $1:elevation as elevation\nfrom @trails_parquet\n(file_format => ff_parquet)\norder by sequence_1;"),
    page("🎯 Create a View with Nice Looking GeoSpatial Columns"),
    sql("nicely_formatted", code("Create a View with Nice Looking")),
    note("The course's select deliberately maps `$1:latitude` to `lng` and `$1:longitude` to `lat` (the file has them swapped; the code comment says \"we did a gut check on this data\")."),
    course("🎯 Create a View Called CHERRY_CREEK_TRAIL: wrap the select in CREATE VIEW, in Mel's database and TRAILS schema, owned by SYSADMIN."),
    sql("create_cherry_creek_trail", "-- Derived solution\ncreate view cherry_creek_trail as\n" + code("Create a View with Nice Looking")),
    page("🥋 Replace It With a Better View"),
    sql("coord_pairs", code("Replace It With a Better View", 0)),
    sql("replace_cherry_creek_trail", code("Replace It With a Better View", 1)),
    page("🥋 Can We Generate a LINESTRING( )?"),
    sql("linestring_10", code("Can We Generate")),
    page("🎯 Generate the Full Trail in a single LINESTRING"),
    sql("linestring_full", "-- Derived solution: change the limit from 10 to 2450 (WKT Playground errors on all 3,500 points)\n" + code("Can We Generate").replace("point_id <= 10", "point_id <= 2450")),
    page("🥋 Explore the geoJSON Files"),
    sql("explore_geojson", "-- DLKW_095: a select on the geoJSON stage with the JSON file format\nselect * from @trails_geojson (file_format => ff_json);"),
    sql("normalize_geojson", code("Explore the geoJSON Files")),
    page("🎯 Create a View for the geoJSON files"),
    course("🎯 Create a View Called DENVER_AREA_TRAILS: wrap the previous select in CREATE VIEW, in Mel's database and TRAILS schema, owned by SYSADMIN."),
    sql("create_denver_area_trails", "-- Derived solution\ncreate view DENVER_AREA_TRAILS as\n" + code("Explore the geoJSON Files")),
    page("🤖 DORA DLKW06"), dora("DLKW06", "CHERRY_CREEK_TRAIL and DENVER_AREA_TRAILS views exist"),
]

# ---------------------------------------------------------------- lesson 7
NB["lesson_07_geospatial_functions"] = preamble("Lesson 7: Exploring GeoSpatial Functions", "Trail lengths, DENVER_AREA_TRAILS_2 and TRAILS_AND_BOUNDARIES.", TRAILS) + [
    page("🥋 Explore GeoSpatial Functions"),
    course("📓 Navigate to docs.snowflake.com and search for \"GeoSpatial Functions\". Outside Snowflake; nothing to run."),
    note("The course says this ST_LENGTH line won't work (DLKW_111). It runs as given and reports the error."),
    sql("st_length_without_conversion", protected(code("Explore GeoSpatial Functions"))),
    course("🎯 TO_GEOGRAPHY Challenge Lab: add TO_GEOGRAPHY() so length_of_trail works (DLKW_112)."),
    sql("st_length_with_to_geography", "-- From screenshot DLKW_112, blur filled in\nselect \n'LINESTRING('||\nlistagg(coord_pair, ',') \nwithin group (order by point_id)\n||')' as my_linestring\n"
        ",st_length(to_geography(my_linestring)) as length_of_trail\nfrom cherry_creek_trail\ngroup by trail_name;"),
    page("🎯 Add Trail Length to Your View"),
    sql("trail_lengths", "-- From screenshot DLKW_113, blur filled in\nselect feature_name\n, st_length(to_geography(whole_object))  as wo_length\n, st_length(to_geography(geometry)) as geom_length\nfrom denver_area_trails;"),
    sql("get_ddl_view", "select get_ddl('view', 'DENVER_AREA_TRAILS');"),
    sql("replace_denver_area_trails", "-- From screenshot DLKW_115 (column order), editing the view definition from get_ddl\ncreate or replace view DENVER_AREA_TRAILS as\nselect\n"
        "$1:features[0]:properties:Name::string as feature_name\n,$1:features[0]:geometry:coordinates::string as feature_coordinates\n,$1:features[0]:geometry::string as geometry\n"
        ",st_length(to_geography(geometry)) as trail_length\n,$1:features[0]:properties::string as feature_properties\n,$1:crs:properties:name::string as specs\n,$1 as whole_object\nfrom @trails_geojson (file_format => ff_json);"),
    sql("check_denver_area_trails", "select * from DENVER_AREA_TRAILS;"),
    page("🥋 Make the Trail Data Align to Work Together"),
    sql("create_denver_area_trails_2", code("Make the Trail Data Align", 0)),
    sql("union_all_trails", code("Make the Trail Data Align", 1)),
    page("🥋 Enhancing the GeoSpatial Trail View"),
    sql("geospatial_calcs", code("Enhancing the GeoSpatial Trail View")),
    course("🥋 Make it a View (DLKW_122): add `create view trails_and_boundaries as` above the select."),
    sql("create_trails_and_boundaries", "-- From screenshot DLKW_122\ncreate view trails_and_boundaries as\n" + code("Enhancing the GeoSpatial Trail View")),
    sql("select_trails_and_boundaries", "select * from trails_and_boundaries;"),
    page("🥋 Creating A Bounding Box Polygon"),
    sql("bounding_box", code("Creating A Bounding Box Polygon")),
    page("🤖 DORA DLKW07"), dora("DLKW07", "trails northern extent"),
]

# ---------------------------------------------------------------- lesson 8
SONRA = "OPENSTREETMAP_DENVER"
NB["lesson_08_marketplace_data"] = preamble("Lesson 8: Supercharging Development with Marketplace Data", "Sonra OpenStreetMap Denver, variables, the DISTANCE_TO_MC UDF and the views over Sonra data.", TRAILS) + [
    page("🥋 Shopping the Marketplace for GeoSpatial Data"),
    course("NOTE: You will need to switch your role to ACCOUNTADMIN to get the share added to your trial. UI steps (DLKW_130, 131): Marketplace → search **Denver** → **OpenStreetMap Denver** (Sonra) → Get; "
           "Options: Database name **OpenStreetMap_Denver**; additional role SYSADMIN → Get."),
    sql("get_sonra_listing", "-- SQL equivalent of Get. Needs the real ACCOUNTADMIN; the listing is Sonra's free OpenStreetMap Denver (GZSVZ3XR0R)\nuse role accountadmin;\n"
        "call system$accept_legal_terms('DATA_EXCHANGE_LISTING', 'GZSVZ3XR0R');\ncreate database " + SONRA + " from listing 'GZSVZ3XR0R';\n"
        "grant imported privileges on database " + SONRA + " to role {{SYSADMIN_ROLE}};\n-- switching roles drops the context, so restore it\nuse role {{SYSADMIN_ROLE}};\nuse warehouse {{WAREHOUSE}};\nuse schema " + TRAILS + ";"),
    page("🥋 Explore the Sonra Views"),
    course("How many tables are available in the Sonra Denver share? Are there fewer tables than views? Of the views, about how many include \"SHOP\" in the view name? And about how many include \"AMENITY\"? (DLKW_135)"),
    sql("sonra_objects", "-- Derived: answers the questions above\nselect table_type, count(*) as objects,\n       count_if(table_name ilike '%SHOP%') as with_shop_in_name,\n       count_if(table_name ilike '%AMENITY%') as with_amenity_in_name\n"
        "from " + SONRA + ".INFORMATION_SCHEMA.TABLES\nwhere table_schema = 'DENVER'\ngroup by table_type;"),
    page("📓 Melanie's Café Location"), md("Reading and map tools only (Google Maps, WKT Playground, geojson.io); nothing to run."),
    page("🥋 Variables and Constants"),
    sql("variables", code("Variables and Constants")),
    sql("constants", "-- From screenshot DLKW_143 (second query): one set of constants and one set of variables\nselect st_distance(\n        st_makepoint('-104.97300245114094','39.76471253574085')\n        ,st_makepoint($loc_lng, $loc_lat)\n        ) as mc_to_cp;"),
    page("🥋 Defining Our Own Function"),
    course("Create a second Schema in Mel's Database and call it LOCATIONS. Make sure it is owned by SYSADMIN."),
    sql("create_locations_schema", "-- Derived solution\nuse role {{SYSADMIN_ROLE}};\ncreate schema MELS_SMOOTHIE_CHALLENGE_DB.LOCATIONS;\nuse schema MELS_SMOOTHIE_CHALLENGE_DB.LOCATIONS;"),
    note("The course's first function block still contains the placeholder `<our function code will be here>`; the second still has `?` for the constants. Both run as given and report the result; the working function follows."),
    sql("udf_template", protected(code("Defining Our Own Function", 0))),
    sql("udf_with_question_marks", protected(code("Defining Our Own Function", 1))),
    sql("udf_two_arguments", "-- Derived solution: the question marks are Melanie's Cafe coordinates\nCREATE OR REPLACE FUNCTION distance_to_mc(loc_lng number(38,32),loc_lat number(38,32))\n  RETURNS FLOAT\n  AS\n  $$\n   st_distance(\n"
        "        st_makepoint('-104.97300245114094','39.76471253574085')\n        ,st_makepoint(loc_lng,loc_lat)\n        )\n  $$\n  ;"),
    sql("test_udf", code("Defining Our Own Function", 2)),
    page("🥋 Analyze Melanie's Competition"),
    sql("juice_bars", code("Analyze Melanie's Competition", 0)),
    course("🎯 Convert the List into a View: COMPETITION, in the LOCATIONS schema, owned by SYSADMIN."),
    sql("create_competition", "-- Derived solution\ncreate view competition as\n" + code("Analyze Melanie's Competition", 0)),
    sql("closest_competitor", code("Analyze Melanie's Competition", 1)),
    sql("udf_geography", code("Analyze Melanie's Competition", 2)),
    sql("closest_competitor_udf", code("Analyze Melanie's Competition", 3)),
    page("📓 Why Are There Two UDFs with the Same Name?"),
    sql("overloaded_udf", code("Why Are There Two UDFs")),
    page("🎯 Analyze Potential Promotion Partners"),
    course("🎯 Create a View of Bike Shops in the Denver Data: DENVER_BIKE_SHOPS, in the LOCATIONS schema, owned by SYSADMIN; include DISTANCE_TO_MELANIES (DLKW_146)."),
    sql("create_denver_bike_shops", "-- From screenshot DLKW_146, blur filled in\ncreate view DENVER_BIKE_SHOPS as\nselect name\n , ST_DISTANCE(\n    st_makepoint('-104.97300245114094','39.76471253574085')\n    , coordinates\n  ) AS distance_to_melanies\n  , coordinates\n"
        "from OPENSTREETMAP_DENVER.DENVER.V_OSM_DEN_SHOP_OUTDOORS_AND_SPORT_VEHICLES\nwhere shop = 'bicycle';"),
    sql("bike_shop_count", "select count(*) as bike_shops from denver_bike_shops;"),
    page("🤖 DORA DLKW08"), dora("DLKW08", "bike shop view distance calculation"),
]

# ---------------------------------------------------------------- lesson 9
NB["lesson_09_external_tables_and_iceberg"] = preamble("Lesson 9: Lions & Tigers & Bears, Oh My!!!", "External tables, the secure materialized view and an Iceberg table.", TRAILS) + [
    page("📓 What Are All These Things?"), md("Reading and quiz only."),
    page("📓 What is a Materialized View?"), md("Reading and quiz only."),
    page("📓 What is an External Table?"), md("Reading and quiz only (DLKW_147-151 are docs screenshots)."),
    page("🥋 Let's Try to Create an External Table"),
    note("The course says this first attempt on an internal stage fails (b4_1.png). It runs as given and reports what happens."),
    sql("external_table_on_internal_stage", protected(code("Let's Try to Create an External Table"))),
    page("🥋 Let's Try That External Table, Again!"),
    course("Create an External Stage for an External Table (1-dlkw, 2-dlkw, 3-dlkw): Catalog → MELS_SMOOTHIE_CHALLENGE_DB → TRAILS → Create → Stage → Amazon S3; Stage Name **EXTERNAL_AWS_DLKW**; URL **s3://uni-dlkw**; no authentication."),
    sql("create_external_stage", "-- SQL equivalent of the Create Stage dialog (2-dlkw)\nuse role {{ADMIN_ROLE}};\nuse warehouse {{WAREHOUSE}};\nuse schema " + TRAILS + ";\ncreate stage EXTERNAL_AWS_DLKW\n  url = 's3://uni-dlkw';\nlist @external_aws_dlkw;"),
    course("Change the length of the file name and change the name of the STAGE to your new External Stage, then run the command again (4-dlkw). After creating the table, run a SELECT * (5-dlkw)."),
    sql("create_external_table", "-- From screenshot 4-dlkw\ncreate or replace external table T_CHERRY_CREEK_TRAIL(\n   my_file_name varchar(100) as (metadata$filename::varchar(100))\n)\nlocation= @external_aws_dlkw\nauto_refresh = true\nfile_format = (type = parquet);"),
    sql("select_external_table", "select * from t_cherry_creek_trail;"),
    page("🥋 Let's Try that Materialized View Again..."),
    sql("create_secure_mv", code("Let's Try that Materialized View Again")),
    sql("select_secure_mv", "-- 8-dlkw: the materialized view over the external table\nselect * from MELS_SMOOTHIE_CHALLENGE_DB.TRAILS.SMV_CHERRY_CREEK_TRAIL;"),
    page("🤖 DORA DLKW09"), dora("DLKW09", "secure materialized view has 3,526 rows"),
    page("📓 What is an Apache Iceberg Table?"), md("Reading and quiz only."),
    page("🥋 Set Up Your Iceberg External Volume and User"),
    course("For the remainder of this workshop, you should do your work using the ACCOUNTADMIN Snowflake role."),
    sql("create_external_volume", "-- Account-level object: runs as the real ACCOUNTADMIN\nuse role accountadmin;\n" + code("Set Up Your Iceberg External Volume")),
    sql("describe_external_volume", code("Set Up Your Iceberg External Volume", 1)),
    note("The course now has the learner enter the volume's `STORAGE_AWS_IAM_USER_ARN` in the YSA badge-management app (DLKW_170). That adds the user to the AWS policy of the course's bucket; it cannot be done from this "
         "account, so the Iceberg table below may fail with an access error until it is done."),
    page("🥋 Set Up Your Apache Iceberg DB and Table"),
    sql("create_iceberg_db", "use role accountadmin;\n" + code("Set Up Your Apache Iceberg DB and Table", 0)),
    sql("iceberg_table_name", "use role accountadmin;\nuse database MY_ICEBERG_DB;\nuse schema PUBLIC;\nuse warehouse {{WAREHOUSE}};\nset table_name = 'CCT_'||current_account();\nselect $table_name;"),
    note("Verified 2026-11-14: creating the table fails with `Error assuming AWS_ROLE ... is not authorized to perform: sts:AssumeRole on resource: arn:aws:iam::321463406630:role/dlkw_iceberg_role`. "
         "The course's AWS role trusts only the volume IAM users that Snowflake Education adds through the YSA app (DLKW_170), which only a learner's course account can do. "
         "The next three cells run as given and report the result, so DLKW10 cannot pass here."),
    sql("create_iceberg_table", "use role accountadmin;\nuse database MY_ICEBERG_DB;\nuse schema PUBLIC;\nuse warehouse {{WAREHOUSE}};\n" + protected(code("Set Up Your Apache Iceberg DB and Table", 1))),
    sql("select_iceberg_table", "use role accountadmin;\nuse database MY_ICEBERG_DB;\nuse schema PUBLIC;\n" + protected(code("Set Up Your Apache Iceberg DB and Table", 2))),
    page("📓 What's the Big Deal Here?"),
    sql("update_iceberg_table", "use role accountadmin;\nuse database MY_ICEBERG_DB;\nuse schema PUBLIC;\n" + protected(code("What's the Big Deal Here"))),
]

# ---------------------------------------------------------------- lesson 10
NB["lesson_10_prototypes_and_pitches"] = preamble("Lesson 10: Prototypes, Pitches, and Proof of Concepts", "Closing lesson and DLKW10.") + [
    page("🏆 Proofs of Concepts = Success"), md("Quiz only."),
    page("⏭️  Moving the Projects Forward"), md("Story only."),
    page("🤖 DORA DLKW10"), dora("DLKW10", "Iceberg table created and populated, 100 rows"),
    page("🎉 Badge Time!"),
    course("Check in with DORA in the YSA app: all DORA tests should be PASSING and VALID. Outside Snowflake; nothing to run."),
    note("The Badge Time page says to look for \"DLKW01 to DLKW09\", but the course has ten tests (DLKW01 to DLKW10)."),
]

# ---------------------------------------------------------------- DORA tests
DORA_PAGES = [("DLKW01", 2), ("DLKW02", 3), ("DLKW03", 4), ("DLKW04", 4), ("DLKW05", 5), ("DLKW06", 6), ("DLKW07", 7),
              ("DLKW08", 8), ("DLKW09", 9), ("DLKW10", 10)]
LESSON_FILE = {2: "lesson_02_data_structures_and_stages", 3: "lesson_03_leaving_data_where_it_lands", 4: "lesson_04_unstructured_data",
               5: "lesson_05_concept_kickoff", 6: "lesson_06_geospatial_views", 7: "lesson_07_geospatial_functions",
               8: "lesson_08_marketplace_data", 9: "lesson_09_external_tables_and_iceberg", 10: "lesson_09_external_tables_and_iceberg"}
dora_cells = [
    md("# Badge 4: DORA checks\n\nEvery DORA step from the course, in order. Each check has two cells:\n\n"
       "1. **Local check**: the course's check query with the external `GRADER` call removed. It runs entirely in this account and sends nothing.\n"
       "2. **DORA (exact course code)**: verbatim and unedited (DORA audits a hash of the code).\n\n"
       "⚠️ **Running a DORA cell sends data outside this account** to Snowflake Education's grading service. Run only the local checks unless you intend to submit.\n\n"
       "Each check is meant to be run at the end of its lesson: later lessons add stages and views that earlier checks count (for example DLKW05 counts the stages and file formats in Mel's database)."),
    md("## Set your worksheet drop lists"),
    py("dora_vars", f'WAREHOUSE = "{WAREHOUSE}"   # stands in for the course\'s COMPUTE_WH'),
    sql("dora_context", "use role accountadmin;\nuse warehouse {{WAREHOUSE}};\nuse database util_db;\nuse schema public;"),
]
for step, lesson in DORA_PAGES:
    c = code(f"DORA {step}")
    local = dora_local(c)
    assert "grader(" not in re.sub(r"--.*", "", local).lower(), step
    dora_cells += [md(f"## {step} (after `{LESSON_FILE[lesson]}`)"), sql(f"{step.lower()}_local", "-- Local check: same query without the GRADER call\n" + local), sql(f"{step.lower()}_dora", c)]
NB[DORA_NB] = dora_cells

# ---------------------------------------------------------------- write
META = {"jupytext": {"main_language": "sql"}, "kernelspec": {"display_name": "Streamlit Notebook", "name": "streamlit"}}
for sub in ("data", "dora", "tools"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
for sub in ("", "dora"):
    for old in [f for f in os.listdir(os.path.join(OUT, sub)) if f.endswith(".ipynb")]:
        os.remove(os.path.join(OUT, sub, old))
for old in os.listdir(os.path.join(OUT, "data")):
    os.remove(os.path.join(OUT, "data", old))
for zname in ZIPS:
    z = zipfile.ZipFile(os.path.join(ASSETS, zname))
    for n in zip_members(zname):
        open(os.path.join(OUT, "data", os.path.basename(n)), "wb").write(z.read(n))
shutil.copy(os.path.join(ASSETS, "cherry_creek_trail.parquet"), os.path.join(OUT, "data", "cherry_creek_trail.parquet"))
for name, cells in NB.items():
    names = [c["metadata"].get("name") for c in cells if c["cell_type"] == "code"]
    assert len(names) == len(set(names)), (name, [n for n in names if names.count(n) > 1])
    json.dump({"cells": cells, "metadata": META, "nbformat": 4, "nbformat_minor": 5},
              open(os.path.join(OUT, f"{name}.ipynb"), "w"), indent=1)
    print(f"{name:46s} cells={len(cells):3d}  code={len(names):3d}")
shutil.copy(os.path.abspath(__file__), os.path.join(OUT, "tools", os.path.basename(__file__)))
print("data files:", len(os.listdir(os.path.join(OUT, "data"))))
