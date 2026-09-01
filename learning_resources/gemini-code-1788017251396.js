(async () => {
    // ============================================================
    //  CONFIGURABLE SETTINGS & USER LIST
    // ============================================================
    const ADMIN_PASS       = "***REMOVED***";
    const API_ENDPOINT     = "./non_agent_api.php";
    const REQUEST_DELAY_MS = 200;

    // Specific target array of users
    const usersList = [
        "8001", "8002", "8003", "8004", "8005",
        "8006", "8007", "8008", "8009", "8010",
        "9001", "9002", "9003", "9004", "9005",
        "9006", "9007", "9008", "9009", "9010",
        "9011", "9012", "9013", "9014", "9015",
        "6666"
    ];

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
    //  PROMPT FOR PASSWORD ONLY
    // ============================================================
    const adminPass = prompt("Enter Admin Password:", ADMIN_PASS);
    if (adminPass === null) {
        console.log("%c[Bulk Update] Cancelled by user.", "color: #888;");
        return;
    }

    if (!adminPass.trim()) {
        console.error("%c[Bulk Update] Error: Admin password cannot be empty.", "color: red; font-weight: bold;");
        alert("Error: Admin password cannot be empty.");
        return;
    }

    const totalUsers = usersList.length;

    // ============================================================
    //  CONFIRMATION
    // ============================================================
    const confirmed = confirm(
        `About to update ${totalUsers} user(s):\n${usersList.join(", ")}\n\n` +
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
    console.log(` Total Users: ${totalUsers}`);
    console.log(` Admin      : ${ADMIN_USER}`);
    console.log(` Endpoint   : ${API_ENDPOINT}`);
    console.log("%c==================================", "color: #015B91; font-weight: bold;");

    let success = 0;
    const failedIDs = [];

    for (let index = 0; index < usersList.length; index++) {
        const currentId = String(usersList[index]);
        const progress  = `[${index + 1}/${totalUsers}]`;

        const queryParams = new URLSearchParams({
            source:        "admin",
            function:      "update_user",
            user:          ADMIN_USER,
            pass:          adminPass.trim(),
            agent_user:    currentId,
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