# START HERE — Creator Reset for iPhone

**What it is:** an iPhone app that sorts your photos and videos into neat review albums, finds possible copies and your longest videos, keeps a log of everything it did, and can run by itself every night through Apple's Shortcuts app. It also adds a Safari helper that can do small, safe steps on a website after you say OK.

**What it never does:** delete your photos, upload your photos, post or delete anything on Instagram, buy things, or sign in for you.

---

## Part A — Put the app on the iPhone (one time, about 20 minutes)

You need: **a Mac**, **the friend's iPhone**, **a USB cable**, and **an Apple Account** (the free one you already have is fine).

1. **On the Mac, get Xcode.** Open the **App Store** app, search **Xcode**, and tap **Get**. It is free. It is big, so it can take a while.
2. **Unzip the project.** Double-click `CREATOR_RESET_BUILD.zip`. You get a folder called `iphone-operator`.
3. **Open the project.** In that folder, double-click **`CreatorReset.xcodeproj`**. Xcode opens.
4. **Sign in to Xcode.** In the top menu, click **Xcode → Settings → Accounts → +** and sign in with your Apple Account.
5. **Pick your team (two times).** In the left sidebar, click the blue **CreatorReset** icon at the very top. In the middle you'll see two names under TARGETS:
   - Click **CreatorReset** → **Signing & Capabilities** tab → **Team** → pick your name.
   - Click **CreatorResetSafari** → **Signing & Capabilities** tab → **Team** → pick your name again.
   - ✅ Success looks like: no red error text under Signing.
   - ❌ If it says the "bundle identifier is not available": click the blue **CreatorReset** project icon (top of the list) → **Build Settings** tab → type `CR_BUNDLE_PREFIX` in the search box → change `com.thenailbawse` to something unique like `com.thenailbawse.amy` → press Return.
6. **Plug in the iPhone.** Unlock it. If it asks **"Trust This Computer?"**, tap **Trust** and type the phone's passcode.
7. **Turn on Developer Mode on the iPhone** (Apple asks for this once): **Settings → Privacy & Security → Developer Mode → On**. The phone restarts. After it restarts, tap **Turn On**.
8. **Choose the iPhone in Xcode.** At the top middle of Xcode, click the device name and pick the friend's iPhone.
9. **Press the ▶ Play button** (top left). Wait. The app appears on the iPhone.
10. **Trust the app on the iPhone** (only the first time): **Settings → General → VPN & Device Management → your Apple Account → Trust**.

> **Free Apple Account note:** apps installed this way **stop opening after 7 days**. To refresh, plug the phone in and press ▶ again (step 9). A paid Apple Developer account ($99/year) makes it last a year — **you don't need it to test.**

---

## Part B — Allow, test, activate (on the iPhone, 10 minutes)

**1. Allow.** Open **Creator Reset**. On **Home**, tap **Allow Photos**.
- Choose **Allow Full Access** to organize everything, or **Limit Access** to pick just some photos.
- ✅ Success: "Photos access" says **Full access** or **Only the photos you picked**.

**2. Practice with fake photos (recommended the first time).** Tap **Add 12 fake test photos**.
- ✅ Success: the message says "Added 12 FAKE test photos." They are pink/blue cards that say FAKE TEST PHOTO.

**3. Test with 5.** Tap **Test with 5 photos**.
- ✅ Success: "Looked at 5 items. Added 5 to review albums. Nothing was deleted or uploaded."
- Open the **Photos** app → **Albums**. You'll see new albums that start with **"Reset ·"**.

**4. Prove it never repeats.** Tap **Test with 5 photos** again.
- ✅ Success: "**Added 0** … 5 were already organized (no repeats)."

**5. Look at the log.** Tap the **Results** tab → tap a run. Each item shows **Before → After**. ✅ means it was added *and checked*.

**6. Clean up the practice.** Home → **Remove the fake test photos** → confirm. The iPhone asks you once more. Only the fake ones go to Recently Deleted.

**7. Run it for real.** Home → pick **How many per run** (start with 20) → **Run Organizer**. Each time you tap it, it continues to the next older photos it hasn't sorted yet.

**8. Check "Needs Review".** Tap the **Review** tab. These are photos the app wasn't sure about. It asks you instead of guessing.

**9. Turn on the nightly run (Activate).**
1. Open the **Shortcuts** app → **Automation** tab → **+**.
2. Tap **Time of Day** → choose **2:00 AM**, **Daily** → choose **Run Immediately** → **Next**.
3. Search **Creator Reset** → tap **Organize Recent Media** → set **How many items** to **50** → **Done**.
4. Next morning: open Creator Reset → **Results**. ✅ A run that says **"Shortcuts"** means it worked by itself.
- If no run shows up: the phone may have been locked too tightly at 2 AM. Try a time when the phone is charging but recently used, like 10 PM.

**10. Free up space (you do this — the app never deletes).**
1. **Photos → Albums → Utilities → Duplicates → Merge** (Apple's own tool keeps the best copy).
2. Look at **Reset · Longest Videos** and **Reset · Screenshots**. Delete what you don't need.
3. **Photos → Albums → Recently Deleted → Select → Delete All.** Space only comes back after this.
4. Open Creator Reset → Home → **Storage** shows "Free space went up by …".
- ⚠️ If iCloud Photos is on, deleting removes the photo from **every** device using that Apple Account.

**11. Safari helper (optional).**
1. **Settings → Apps → Safari → Extensions → Creator Reset → On.**
2. Open Safari, go to a normal website (not a bank, not email). Tap the **aA** or puzzle icon → **Creator Reset** → **Allow** for this website.
3. Tap **Inspect this page** → type what you want → **Plan with on-device AI** (newer iPhones) or **Copy for ChatGPT / Claude** → read the steps → **Approve & run**.
- It refuses sign-in pages, payments, posting, sending and deleting. It stops after each tap so you can check.

**12. Instagram reset.** Help tab → **Instagram reset**.
- Your posting queue is the album **Reset · Creator Content**.
- Archive old posts yourself in Instagram: open the post → **•••** → **Archive** (you can undo it).
- **Copy: Meta AI (Muse) audit prompt** → paste into Meta AI. It asks Meta AI to tell you what it can and can't do **before** it does anything.

---

## How to STOP or take it back (any time)

| I want to… | Do this |
| --- | --- |
| Stop all changes right now | Creator Reset → Home → **Pause the operator** |
| Take away photo access | Settings → Apps → Creator Reset → Photos → **None** |
| Stop the nightly run | Shortcuts → Automation → swipe left on it → **Delete** |
| Turn off the Safari helper | Settings → Apps → Safari → Extensions → Creator Reset → **Off** |
| Remove the app | Press and hold the icon → **Remove App** (photos and albums stay) |
| Undo the albums | Photos → Albums → press and hold a "Reset ·" album → **Delete Album** (deleting an album does **not** delete the photos in it) |

---

## What has been tested, and what has not

| Part | Status |
| --- | --- |
| Sorting rules, no-repeat log, safety rules, web-plan checker (26 automated tests) | ✅ Tested by computer |
| Safari helper safety logic (8 automated tests in a fake browser) | ✅ Tested by computer |
| App compiles for iPhone and iPhone Simulator | See `README.md` → "Build status" (checked automatically on every change) |
| Photos flow on the iPhone Simulator: fake photos → test 5 → test 5 again adds 0 → pause blocks changes | See `README.md` → "Build status" |
| On a real iPhone: permissions, albums, Shortcuts, nightly run | ⏳ **Not tested yet** — that's Part B above |
| On-device AI ("Ask" tab, Safari planning) | ⏳ **Not tested yet** — needs iPhone 15 Pro or newer with iOS 26 and Apple Intelligence on |
| Overnight background time (the Help tab switch) | ⏳ **Not tested** — iOS decides if it ever runs |
| Meta AI / Muse with Instagram | ⏳ **Not tested** — we don't know what it can do yet; the audit prompt finds out |

**Please write down after testing:** iPhone model, iOS version, how many photos were sorted, anything that failed, and whether the 2 AM run showed up in Results.
