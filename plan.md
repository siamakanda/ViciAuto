# So lets talk about what this application is for and we will define its architecture, workflow and logics here.
#### The application is to autmate vicidialer bulk tasks for my voip service company. The application can already perform many tasks like:
Saved profiles:
-----------------------------------------------------------------
  [1] example         -> https://dm23.callengine.org  (user: 6666)  [no-verify]
  [2] dm3             -> https://dm3.callengine.org  (user: 6666)  [no-verify]
  [3] DX6             -> https://dx6.callengine.org  (user: 6666)  [no-verify]
  [4] DM2             -> https://dm2.callengine.org  (user: 6666)  [no-verify]
  [5] TeleMusketeers  -> https://tm.callengine.org  (user: 6666)  [no-verify]
-----------------------------------------------------------------
  [N] New login / add profile
  Select profile [1-5] or N: 3

════════════════════════════════════════════════════════════
  Bulk Operations — DX6 (https://dx6.callengine.org)
════════════════════════════════════════════════════════════
  1. Update User Phones & Pass   (range / CSV)
  2. Bulk Phone Creation / Copy   (range / CSV)
  3. Bulk Phone Delete & Alias Delete (range / CSV)
  4. Delete All Phones & Phone Alias List
  5. Switch profile
  0. Back
════════════════════════════════════════════════════════════
  Select option: 

#### Now Im Thinking to upgrade it more and need your help crafting it better.
## a. When starts, show saved dialers to choose and show option to add a new dialer or remove or change credentials of an existing dialer profile.

### 1. If choose a diler, go to the next steps of the flow. Show the "Bulk Task Menu"
### 2. If add a diler, add the dialer
### 3. If remove a diler, remove the diler
### 4. If choose change credentials of a diler, change credentials.

#### a1. The menu should show these list of bulk tasks.
  1. Bulk Profile Creation
  2. Bulk Phone Creation
  3. Bulk Profile and Phone Bonding
  4. Bulk Profile Delete 
  5. Bulk Phone Delete & Alias Delete
  6. Import full csv (or better data import type if possible) dialer profile.
  7. Switch profile
  0. Back


#### This response is from gemeni. see if it helps or not.
Let's structure and refine the architecture for this upgrade. Below is the blueprint covering the enhanced workflow, data layer, core application logic, and implementation considerations.

---

### Application Architecture & Workflow

```
[ Application Startup ]
          │
          ├──> [ Profile Management Menu ]
          │          ├── (1) Select Existing Dialer ──────┐
          │          ├── (2) Add New Dialer               │
          │          ├── (3) Remove Dialer                │
          │          └── (4) Edit Dialer Credentials      │
          │                                               │
          └───────────────────────────────────────────────┘
                                  │
                                  ▼
                     [ Main Bulk Task Menu ]
                          │
                          ├── 1. Bulk User/Profile Creation
                          ├── 2. Bulk Phone Creation
                          ├── 3. Bulk Profile & Phone Bonding
                          ├── 4. Bulk User/Profile Delete
                          ├── 5. Bulk Phone & Alias Delete
                          ├── 6. Dynamic CSV / Spec Import
                          ├── 7. Switch Dialer Profile
                          └── 0. Exit / Back

```

---

### Profile Management Logic

Store credentials securely (e.g., encrypted SQLite DB or a JSON file with `keyring`/fernet encryption instead of plain text).

* **Select Profile:** Loads base URL, API/admin user, pass, and SSL verification flag into the current active session context.
* **Add Profile:** Prompts for `Label`, `Base URL`, `Admin User`, `Admin Pass`, and `SSL Verification (y/n)`. Validates connection via Vicidial API (`version` call or basic auth check) before saving.
* **Remove Profile:** Prompts for selection, requests confirmation (`y/N`), and purges the record.
* **Edit Credentials:** Allows updating `Admin User`, `Admin Pass`, or `Base URL` for a specific saved label without re-creating it.

---

### Core Task Breakdown & Logics

#### 1. Bulk Profile Creation (Vicidial Users)

* **Inputs:** CSV file (Columns: `user`, `pass`, `full_name`, `user_level`, `user_group`) or automated range generation (`user_start`, `user_end`, default password pattern).
* **API Route:** `non_agent_api.php?function=add_user`
* **Logic:** Iterates through records, validates minimum password complexity (Vicidial specs), executes API request, and logs results (Success/Failed/Skipped if already exists).

#### 2. Bulk Phone Creation

* **Inputs:** Range (e.g., `1001-1100`) or CSV (`extension`, `dialplan_number`, `voicemail_id`, `phone_login`, `phone_pass`).
* **API Route:** `non_agent_api.php?function=add_phone`
* **Logic:** Sets standard parameters (Protocol: SIP/WebRTC, Server IP, Registration status). Creates associated phone alias records if specified in the payload.

#### 3. Bulk Profile & Phone Bonding

* **Inputs:** CSV mapping file or dual range (`user_range`, `phone_range`).
* **Logic:**
* Fetches target Vicidial User.
* Updates `phone_login` / default phone context in Vicidial user configuration via API or database update.
* Sets up webphone / phone alias mappings if using WebRTC setup.



#### 4. Bulk Profile Delete

* **Inputs:** Range or CSV list of User IDs.
* **API Route:** `non_agent_api.php?function=delete_user` or direct API cleanup.
* **Logic:**
* Prompts for double confirmation showing count of targeted users.
* Checks if target users are currently logged in before issuing deletion requests.



#### 5. Bulk Phone & Alias Delete

* **Inputs:** Range or CSV list of phone extensions/aliases.
* **API Route:** `non_agent_api.php?function=delete_phone` and `delete_phone_alias`.
* **Logic:** Purges target extensions and drops associated entries from `vicidial_phone_aliases`.

#### 6. Smart CSV / Data Import Engine

Instead of rigid CSV columns, implement a **Header Mapping Engine**:

* **Parser:** Dynamically reads CSV headers.
* **Field Mapping:** Maps input CSV columns to Vicidial parameters (e.g., CSV column `Extension` $\rightarrow$ Vicidial `extension`).
* **Multi-Task Execution:** Auto-detects if a row contains both phone and user data, then runs **Creation $\rightarrow$ Phone Creation $\rightarrow$ Bonding** sequentially in a single pass.

#### 7. Switch Profile

* Clears active session credentials and loops back to the main Profile Management Menu.

---

### Implementation & Interface Enhancements

* **Session & Connection Wrapper:** Abstract all HTTP API calls through a centralized request handler that automatically appends auth parameters (`source=automation_app`, `user`, `pass`) and handles rate-limiting and connection timeouts.
* **Dry-Run Mode:** Option to run any bulk operation in `Preview Mode` to parse inputs, validate syntax, and preview the affected targets before executing against Vicidial.
* **Structured Audit Logging:** Log every bulk action to a timestamped log file (`logs/bulk_ops_YYYYMMDD.log`) containing timestamp, target profile URL, executed task, successful IDs, and failure reasons.