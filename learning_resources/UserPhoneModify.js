(async () => {
    // ============================================================
    //  CONFIGURABLE SETTINGS — tweak these defaults as needed
    // ============================================================
    const ADMIN_PASS      = "";  // never hardcode credentials - enter at the prompt
    const API_ENDPOINT    = "./non_agent_api.php";
    const REQUEST_DELAY_MS = 200;
    const DEFAULT_START   = 5001;
    const DEFAULT_END     = 5015;

    // ============================================================
    //  DETECT / FALLBACK ADMIN USER
    // ============================================================
    const ADMIN_USER = (() => {
        if (typeof user !== "undefined" && user) {
            return String(user);
        }
        console.warn(
            "%c⚠ Admin user not found in scope. Falling back to default: '6666'.",
            "color: #e6a817; font-weight: bold;"
        );
        return "6666";
    })();

    // ============================================================
    //  PROMPTS — range & password
    // ============================================================
    const startRaw = prompt(`Enter Start Range (e.g., ${DEFAULT_START}):`, DEFAULT_START);
    if (startRaw === null) {
        console.log("%c[Bulk Update] Cancelled by user.", "color: #888;");
        return;
    }
    const endRaw = prompt(`Enter End Range (e.g., ${DEFAULT_END}):`, DEFAULT_END);
    if (endRaw === null) {
        console.log("%c[Bulk Update] Cancelled by user.", "color: #888;");
        return;
    }
    const adminPass = prompt("Enter Admin Password:", ADMIN_PASS);
    if (adminPass === null) {
        console.log("%c[Bulk Update] Cancelled by user.", "color: #888;");
        return;
    }

    // ============================================================
    //  VALIDATION
    // ============================================================
    const startRange = parseInt(startRaw, 10);
    const endRange   = parseInt(endRaw, 10);

    if (isNaN(startRange) || isNaN(endRange)) {
        console.error("%c[Bulk Update] Error: Range values must be numeric.", "color: red; font-weight: bold;");
        alert("Error: Range values must be numeric.");
        return;
    }
    if (!adminPass.trim()) {
        console.error("%c[Bulk Update] Error: Admin password cannot be empty.", "color: red; font-weight: bold;");
        alert("Error: Admin password cannot be empty.");
        return;
    }
    if (startRange <= 0 || endRange <= 0) {
        console.error("%c[Bulk Update] Error: Range values must be positive (greater than zero).", "color: red; font-weight: bold;");
        alert("Error: Range values must be positive.");
        return;
    }
    if (startRange > endRange) {
        console.error("%c[Bulk Update] Error: Start range cannot be larger than End range.", "color: red; font-weight: bold;");
        alert("Error: Start range cannot be larger than End range.");
        return;
    }

    const totalUsers = endRange - startRange + 1;

    // ============================================================
    //  CONFIRMATION
    // ============================================================
    const confirmed = confirm(
        `About to update ${totalUsers} user(s) (${startRange} through ${endRange})\n` +
        `Admin user: ${ADMIN_USER}\n` +
        `Endpoint: ${API_ENDPOINT}\n\n` +
        `Proceed?`
    );
    if (!confirmed) {
        console.log("%c[Bulk Update] Aborted by user at confirmation.", "color: #888;");
        return;
    }

    // ============================================================
    //  PROCESS
    // ============================================================
    console.clear();
    console.log("%c==================================", "color: #015B91; font-weight: bold;");
    console.log("%c Bulk Phone Updater", "color: #015B91; font-weight: bold;");
    console.log(` Range      : ${startRange} → ${endRange}  (${totalUsers} users)`);
    console.log(` Admin      : ${ADMIN_USER}`);
    console.log(` Endpoint   : ${API_ENDPOINT}`);
    console.log("%c==================================", "color: #015B91; font-weight: bold;");

    let success   = 0;
    const failedIDs = [];

    for (let i = startRange; i <= endRange; i++) {
        const currentId = String(i);
        const progress  = `[${i - startRange + 1}/${totalUsers}]`;

        const queryParams = new URLSearchParams({
            source:       "admin",
            function:     "update_user",
            user:         ADMIN_USER,
            pass:         adminPass.trim(),
            agent_user:   currentId,
            user_password: currentId,
            phone_login:   currentId,
            phone_pass:    currentId
        });

        try {
            const response = await fetch(`${API_ENDPOINT}?${queryParams.toString()}`);

            if (response.ok) {
                console.log(
                    `%c${progress} User ${currentId}: %c✅ Updated`,
                    "font-weight: bold;",
                    "color: green; font-weight: bold;"
                );
                success++;
            } else {
                console.error(
                    `%c${progress} User ${currentId}: %c❌ HTTP ${response.status} ${response.statusText}`,
                    "font-weight: bold;",
                    "color: red; font-weight: bold;"
                );
                failedIDs.push(currentId);
            }
        } catch (err) {
            console.error(
                `%c${progress} User ${currentId}: %c❌ Network error — ${err.message}`,
                "font-weight: bold;",
                "color: red; font-weight: bold;"
            );
            failedIDs.push(currentId);
        }

        await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
    }

    // ============================================================
    //  SUMMARY
    // ============================================================
    const failedCount = failedIDs.length;
    const summaryLines = [
        `Updated: ${success}`,
        `Failed:  ${failedCount}`
    ];
    if (failedCount > 0) {
        summaryLines.push(`Failed IDs: ${failedIDs.join(", ")}`);
    }

    console.log("%c==================================", "color: green; font-weight: bold;");
    console.log(`%c${summaryLines.join(" | ")}`, "color: green; font-weight: bold;");
    console.log("%c==================================", "color: green; font-weight: bold;");

    alert(`Done!\n\n${summaryLines.join("\n")}`);
})();
