# Aurelune: 4-person presentation script

**About 17 minutes** (you can skip the parts marked optional). Two people present the **virtual machine** and two people present the **e-commerce site**.
Each person has a "Do" (what to click or type) and a "Say" (what to tell the class), plus the **rubric item** it earns.
Say it in your own words. The "Say" lines are a guide, not something to memorise.

| Speaker | Part | Time | Hands over to |
|---|---|---|---|
| **Speaker 1** | Intro + the virtual machine: setup and network | 3.5 min | Speaker 2 |
| **Speaker 2** | The virtual machine: running, checking, staying up | 4 min | Speaker 3 |
| **Speaker 3** | The e-commerce site: shopping as a buyer | 5 min | Speaker 4 |
| **Speaker 4** | The e-commerce site: sellers, admin, APIs, code + closing | 4.5 min | Questions |

Write your names here: Speaker 1 ______ · Speaker 2 ______ · Speaker 3 ______ · Speaker 4 ______

## The two grading rubrics, row by row

Every row of both rubrics (Integrative Programming Technologies and Platform Technologies) is shown by someone below.
Look for the **Rubric items** line at the top of each speaker's part.

| Rubric row | Points | Where it is shown | Speaker |
|---|---|---|---|
| **IPT: Core e-commerce** (sign-in, catalog and search, bag updates, checkout, order history, sold-out and empty-bag cases) | 25 | Browsing, bag change and remove, checkout, order history, empty bag, sold-out watch | 3 and 4 |
| **IPT: API integration and design** (2 or more APIs, proper HTTP methods, clean JSON, status codes, error and timeout handling) | 25 | `api-demo.sh`: GET, POST, PATCH, DELETE, codes 200 to 504, own REST API plus Frankfurter and Mapbox/OpenStreetMap | 4 (and 3 for currency and map) |
| **IPT: Python back end and database** (modular code, related tables, password hashing, validation) | 20 | Code structure, enforced table links, hashed passwords, validation, 335 tests | 4 |
| **IPT: Virtual machine and localhost** (isolated dependencies, services start cleanly, port forwarding works) | 15 | VM settings, `.venv`, service, port forwarding, Windows browser | 1 and 2 |
| **IPT: UI/UX and documentation** (clear feedback, responsive, README, requirements.txt, API docs, well-paced demo) | 15 | Narrow-window layout, error messages, README, `requirements.txt`, `/api/docs`, `docs/API.md` | 3, 2, 4 |
| **PlatTech: Error-free execution on the VM** | 35 | Health check, clean log, every page 200, no errors during the demo | 2 |
| **PlatTech: Localhost and VM network configuration** | 25 | NAT, port-forward rule 5000 to 5000, Windows browser opens the store, no port conflicts | 1 and 2 |
| **PlatTech: VM provisioning and environment setup** (resources, isolated runtime, variables, no missing modules) | 20 | Memory, CPUs, disk, `.venv`, `.env`, `requirements.txt`, package check | 1 |
| **PlatTech: Service and database reliability** | 10 | `systemctl status`, restart, auto-restart, database checks, API connections | 2 |
| **PlatTech: VM verification and setup documentation** | 10 | `vm-check.sh`, journal log, README and PDF guide, smooth walkthrough | 2 |

---

## Before you start (everyone, 10 minutes earlier)

1. The VM is **running**. In the VM's terminal, in the `FREE` folder, run `bash scripts/vm-check.sh`. It must end with **VM CHECK: everything is OK.**
2. Open these **before** the audience arrives:
   - **VirtualBox Manager** (the window with the VM list).
   - The VM's **Terminal**, already inside the folder (type `cd ~/FREE`). Make the text bigger with **Ctrl and +**.
   - The store in **Windows' own browser**: `http://127.0.0.1:5000`. This proves port forwarding works.
3. Accounts that must already exist (create them at home):
   - **Admin**: made with "Set up the admin account" or `create-admin`.
   - **Buyer**: `buyer@example.com`, a normal account.
   - **Shop owner**: `shop@example.com`, a normal account that has **already applied** under *Sell on Aurelune* and is still **waiting** (Speaker 4 will approve it live).
4. Keep every password on a paper next to you, not on screen.
5. Zoom the browser to 125% (**Ctrl and +**) so the back row can read it.

---

## Speaker 1: Intro and the virtual machine setup (3.5 min)

**Rubric items:** VM provisioning and environment setup · localhost and network configuration

**1. Introduce the team and the project (30 sec)**
- **Do:** Show the store's homepage in the browser.
- **Say:** "Good day, everyone. We are group ______. This is **Aurelune**, an online watch store we built with **Python and Flask**. Today we show two things. First, the **virtual machine** that runs it, which [Speaker 2] and I will present. Then the **store itself**, which [Speaker 3] and [Speaker 4] will present."

**2. What the VM is and why we use it (20 sec)**
- **Do:** Switch to the **VirtualBox Manager** window and select the VM called Aurelune.
- **Say:** "A virtual machine is a whole computer running inside our computer. We used **Oracle VirtualBox** with **Ubuntu Linux 26.04 LTS**. The store runs *inside* the VM, so it does not depend on the school PC. If something breaks, only the VM is affected."

**3. The VM's resources (40 sec)**
- **Do:** Click **Settings → System**. Show **Base Memory** and the **Processor** tab. Then click **Storage** and point to the disk.
- **Say:** "We gave the VM **[4 GB] of memory, [2] processors and a [25 GB] disk**, and hardware virtualization is turned on, so it runs fast. (Say the real numbers you see on screen.)"

**4. The network and port forwarding (60 sec)**
- **Do:** Click **Network → Adapter 1**. Show **Attached to: NAT**. Then click **Port Forwarding** and point to the rule: **TCP, Host port 5000, Guest port 5000**.
- **Say:** "The VM is on a private network, **NAT**, and has its own private address, **10.0.2.15**. To reach the store from Windows, we added a **port-forwarding rule**: anything sent to port **5000** on this computer goes to port **5000** inside the VM. That is why we can open the store in a normal Windows browser at **127.0.0.1, port 5000**."

**5. How we installed it, with one command (60 sec)**
- **Do:** Switch to the VM's **Terminal**. Type each line and pause after it:
```bash
ls
```
```bash
head -8 requirements.txt
```
```bash
grep -E "^(HOST|PORT)" .env
```
```bash
ls -a | grep -E "venv|env"
```
- **Say:** "Everything is set up by **one command**, `bash scripts/vm-setup.sh`. It installs Python, then creates an **isolated environment** called `.venv`, so the store's packages do not mix with the system. The exact package versions are listed in **requirements.txt**. It writes a `.env` file for the settings: the host is `0.0.0.0`, so port forwarding can reach it, and the port is `5000`. It creates the database, and installs a **service**, which my teammate will show you."
- **Hand over:** "Now [Speaker 2] will show that everything is really running and healthy."

---

## Speaker 2: The virtual machine, running and staying up (4 min)

**Rubric items:** error-free execution on the VM · service and database reliability · VM verification and documentation

**1. The health check (90 sec)**
- **Do:** In the Terminal, run the command below. When it finishes, scroll up slowly and point at each green **OK** group.
```bash
bash scripts/vm-check.sh
```
- **Say:** "We wrote a health-check script. It tests everything and prints **OK** or **FAIL**. It checks: the VM's **memory and disk**; the **isolated environment**, with no package conflicts; the **database**, whose file is intact and whose links between tables are enforced; that the store has **60 products loaded**; that the store is **listening on port 5000**; and that **every main page answers with status 200**, each in a few milliseconds. The last line says **everything is OK**, and there are **no errors in the log**."

**2. The service (45 sec)**
- **Do:** Run the command below. Point to **active (running)** and **enabled**, then press **q** to leave.
```bash
sudo systemctl status aurelune
```
- **Say:** "The store runs as a **service** called `aurelune`. **Active (running)** means it is up right now. **Enabled** means it starts by itself whenever the VM turns on, so nobody has to type a command. If it ever crashes, it **restarts automatically** after three seconds."

**3. Restart and prove it comes back (45 sec)**
- **Do:** Run these two lines. If the second says "connection refused", wait 5 seconds and run it again.
```bash
sudo systemctl restart aurelune
```
```bash
curl -s http://127.0.0.1:5000/healthz
```
- **Say:** "Let's restart it on purpose. After a few seconds, the health address answers **status ok, database ok**. The store is back without any manual setup."
- **Optional, only if you rehearsed it:** to show a crash recovery, run `sudo pkill -9 -f serve.py`, wait 5 seconds, then run `sudo systemctl status aurelune`. The process number is new, which shows systemd restarted it.

**4. The live log (30 sec)**
- **Do:** Run:
```bash
journalctl -u aurelune -n 12 --no-pager
```
- **Say:** "Here is the service's live log. We see the requests being served and **no tracebacks or errors**."

**5. Proof from Windows (30 sec)**
- **Do:** Go to the **Windows browser** and reload `http://127.0.0.1:5000`. Show the homepage.
- **Say:** "And from outside the VM, the store answers at **127.0.0.1, port 5000**. The network and port forwarding work with no conflicts. The setup steps and this health script are written in our **README** and in `docs`, so anyone can repeat this."
- **Hand over:** "Now [Speaker 3] will show you the store itself."

---

## Speaker 3: The e-commerce site, shopping as a buyer (5 min)

**Rubric items:** core e-commerce functionality · outside API · UI and UX

**1. Browsing (50 sec)**
- **Do:** Show the homepage. Open **Shop ▾** and point to the six collections. Click one (for example **Chronographs**). Type `blue` in the search box and press Enter. Then sort by price.
- **Say:** "This is the buyer's view. We sell **60 watches in 6 collections**: dress, dive, chronographs, field and pilot, smart, and ladies' watches. You can **search, filter and sort**."

**2. One watch in detail (70 sec)**
- **Do:** Open **Riviera Blue Chrono 41**. Press **360° View** and drag left and right. Choose a **case size** and type an **engraving** such as `MJ`. Point to the extra engraving fee. Press **Add to bag** and show the bag drawer. Click **View bag** to open the full bag page, press **+** to raise the quantity, then **−** back down.
- **Say:** "Each watch has a **360-degree view** you can drag. The buyer picks a **case size** and **colour** and can add a personal **engraving**, which adds a fee. The server checks every choice, so the price cannot be changed from the browser. In the bag we can **change the quantity or remove** an item, and the total updates. The bag keeps one line for each combination."

**3. Currency, an outside API (25 sec)**
- **Do:** Click the **PHP** button in the header and choose **USD**. Then switch back to **PHP**.
- **Say:** "The **PHP** button shows prices in other currencies. The rates come from an outside API, **Frankfurter**, which publishes European Central Bank rates. They are only estimates; **orders are always charged in pesos**."

**4. Sign in and checkout (90 sec)**
- **Do:** Click **Sign in** and use the buyer account. Open the bag and press **Checkout**. In the phone box, choose **Philippines** and type a number. Show that extra digits are blocked. Click the **map** to drop a pin and show the address fill in. In the discount box, type `SUMMER25` and show the error, then type `WELCOME10`. Press **Place order**.
- **Say:** "At checkout the **phone number is checked per country**. A Philippine number must be 11 digits starting with 0. The buyer can **drop a pin on the map**, and the address fills in using the **Mapbox and OpenStreetMap** location services. This discount code, SUMMER25, has expired, so the store says so. WELCOME10 works and takes 10 percent off. Payment uses **demo credit**, so no real money or card numbers are involved. Every buyer starts with 500,000 pesos."

**5. The order and history (25 sec)**
- **Do:** On the confirmation page, point to the order number. Click **My account → Orders**, open the order, and point to the bell icon for notifications.
- **Say:** "The order is **saved in the database**, and the buyer can see it in **order history** with a status and a notification. Pressing the button twice never makes two orders, because each checkout has a one-time token."

**6. An empty bag and the phone layout (30 sec)**
- **Do:** Click the **bag** icon. It is empty now, so point to the friendly empty-bag message. Then **drag the edge of the browser window narrow** (or press **F12** and click the phone icon) and show the menu turning into the **☰ button**.
- **Say:** "After the order, the bag is empty, and the store says so politely instead of showing an error. The same page also works on a **phone-size screen**: the menu folds into one button and nothing is cut off."
- **Hand over:** "That was the buyer's side. [Speaker 4] will show the people who run the store, and what is under the hood."

---

## Speaker 4: Sellers, admin, APIs and the code, then closing (4.5 min)

**Rubric items:** API integration and design · Python back end and database · documentation · edge cases

**1. Selling needs approval (45 sec)**
- **Do:** Sign out. Sign in as the **admin**. Open **Admin → Seller requests**. Point to the waiting request from `shop@example.com` and click **Approve**.
- **Say:** "Anyone can register as a buyer, but **selling needs approval**, like Lazada or Shopee. A buyer applies with a shop name and phone number, and **only the admin** can approve or reject. When we approve, the buyer gets a notification and a **seller profile**."

**2. Seller studio and a sold-out watch (50 sec)**
- **Do:** Open **Seller studio → Products**. Open any watch and set **Stock** to `0`, then **Save**. In the other browser tab, reload that watch's page and show **Sold out**. Then open **Orders**, open the buyer's order, and change its status to **Delivered**.
- **Say:** "Staff manage products, stock and orders here. When stock reaches zero, the buyer sees **Sold out** and cannot add it to the bag. Orders move through allowed steps only, from pending to delivered. Everything is saved in the database, and admin actions are written in an **audit log**."

**3. Our own REST API (100 sec)**
- **Do:** Open `http://127.0.0.1:5000/api/docs` and point to the table of endpoints. Then in the VM Terminal, run the command below. Enter the buyer's email and password, press **Enter** to move through each step (about 5 seconds per step), and read the status codes aloud.
```bash
bash scripts/api-demo.sh
```
- **Say:** "The store has its own **REST API** with proper methods: **GET to read, POST to create, PATCH to change, DELETE to remove**. This script walks through it in 15 steps. We search products. A request with no token gets **401 Unauthorized**. We sign in and get a **token**. A wrong size is refused with **422** and a clear message. We **create** a bag line and get **201 Created**, **update** its quantity with PATCH, and **delete** it and get **204**. Ordering with an empty bag is refused with **409 Conflict**. We place an order, and sending the **same request again** returns the same order, not a second one. Then it calls two **outside APIs through ours**: **Frankfurter** for exchange rates and **Mapbox or OpenStreetMap** to turn a map pin into an address. If either is down or slow, our API answers with a clear **503, 502 or 504** error instead of crashing. The last step is **full create, update and delete on products**, which only staff can do. A normal buyer gets **403 Forbidden**."
- **Tip:** At the admin email question, type the admin's email and password to run step 15. Pressing Enter skips it.

**4. Behind the scenes (45 sec)**
- **Do:** In the Terminal, run these two lines. The first shows the code folders; the second shows the database checks.
```bash
ls velora velora/blueprints
```
```bash
.venv/bin/python -m flask --app wsgi doctor | grep -E "Foreign|Schema|integrity|Catalog"
```
- **Say:** "The back end is **Python with Flask**, split into clear parts: **models** for the database, **blueprints** for each area such as shop, account, seller, admin and API, and **services** for the business rules. The data lives in a **SQLite database** with **enforced links between tables**, so for example an order cannot point to a user who does not exist. Passwords are **hashed**, never stored as plain text, and every form is validated on the server and protected from forged requests. We have **335 automated tests**, including one that opens every link as a visitor, buyer, seller and admin to make sure no page is broken."

**5. Closing (20 sec)**
- **Say:** "To summarise: the store runs inside a VM with a one-command setup, a health check, and a service that restarts itself. It has a full shopping flow, seller approval, an admin console, and its own REST API plus two outside APIs. Thank you. We're happy to take questions."

---

## Questions you may get (anyone can answer)

| Question | Short answer |
|---|---|
| Why Flask? | It is a lightweight Python framework. We use blueprints for structure, SQLAlchemy for the database, and Alembic for safe database changes. |
| Which are your APIs? | Our own REST API, plus two outside ones: **Frankfurter** for currency rates, and **Mapbox / OpenStreetMap Nominatim** for map addresses. |
| What if an outside API is down? | The store keeps working. Prices stay in pesos, the address can be typed, and our API replies with 502, 503 or 504. |
| How are passwords protected? | They are hashed, there is a lockout after repeated wrong tries, and sign-in is rate-limited. |
| Is the payment real? | No. It is a demo with fake credit. No card data is collected. |
| How do you stop double orders? | Each checkout has a one-time token, and the API accepts an Idempotency-Key. |
| Why NAT and port forwarding? | NAT keeps the VM isolated. A single forwarded port is all that is opened. |
| What if the VM reboots? | The `aurelune` service starts the store by itself. |
| What if port 5000 is busy? | The store prints a clear message, and you can use another port with `PORT=5050`. |
| Can the database lose data on updates? | No. Updates use migrations, and the start-up script never deletes accounts or orders. |
| Who can approve sellers? | Only an admin. |
| Why SQLite and not MySQL or PostgreSQL? | SQLite is a real relational database with enforced foreign keys, transactions and migrations. It lives inside the app as one file, so there is no separate database server to fail inside the VM. The code uses an ORM (SQLAlchemy), so changing the `DATABASE_URL` setting moves it to another database. |
| Why no real payment or shipping API? | It is a demonstration store, so payment uses demo credit by design and no card data is ever collected. We integrated two outside APIs that work without any payment account: Frankfurter and Mapbox/OpenStreetMap. |
| How did you test it? | 335 automated tests, a crawler that opens every link as visitor, buyer, seller and admin, and the `vm-check.sh` health check inside the VM. |
| Where is the documentation? | `README.md`, `docs/API.md`, `docs/DEMO.md`, `docs/aurelune-process-flow.pdf` and `requirements.txt`. |

---

## If something goes wrong

| Problem | Fix (stay calm and say "let me show that again") |
|---|---|
| The page won't open in Windows | In the VM Terminal run `bash scripts/vm-check.sh`. If it says the store is not running, run `sudo systemctl restart aurelune`. Then check the port-forward rule. |
| "Port 5000 is already in use" | The store is already running: just open the page. |
| Map or currency says unavailable | The VM has no internet right now. Say: "this is the graceful error handling", and show **Admin → API health**. The rest keeps working. |
| `api-demo.sh` says the store isn't answering | `sudo systemctl restart aurelune`, wait 10 seconds, and run it again. |
| You typed a command wrong | Press the **up arrow** to bring back the last command, fix it, and press Enter. |
| You forgot the login | Use the paper with the passwords. The buyer and admin accounts were made before the presentation. |
