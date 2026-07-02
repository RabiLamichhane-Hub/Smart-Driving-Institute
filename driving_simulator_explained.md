# Phaser.js Driving Simulator — Complete Explanation

> This document explains **everything** about the driving simulator we are building — what it is, how it works, why every piece exists, and how all the parts connect together. No code is included. Think of this as the "blueprint narrative" before construction begins.

---

## Table of Contents

1. [What We Are Building](#1-what-we-are-building)
2. [How It Fits Into Your Existing Project](#2-how-it-fits-into-your-existing-project)
3. [The Technology Choice — Why Phaser 3](#3-the-technology-choice--why-phaser-3)
4. [Overall Architecture](#4-overall-architecture)
5. [File-by-File Breakdown](#5-file-by-file-breakdown)
6. [Prompt 1 — Phaser Setup & Car Movement](#6-prompt-1--phaser-setup--car-movement)
7. [Prompt 2 — Track Boundaries](#7-prompt-2--track-boundaries)
8. [Prompt 3 — Scoring System](#8-prompt-3--scoring-system)
9. [Prompt 4 — Checkpoints](#9-prompt-4--checkpoints)
10. [Prompt 5 — Traffic Lights](#10-prompt-5--traffic-lights)
11. [Prompt 6 — Reverse Parking](#11-prompt-6--reverse-parking)
12. [Prompt 7 — Django Backend Integration](#12-prompt-7--django-backend-integration)
13. [Prompt 8 — Two-Wheeler Mode](#13-prompt-8--two-wheeler-mode)
14. [How All Modules Connect Together](#14-how-all-modules-connect-together)
15. [The Game Loop — What Happens Every Frame](#15-the-game-loop--what-happens-every-frame)
16. [Security & CSRF Handling](#16-security--csrf-handling)
17. [What the User Sees — The Complete Flow](#17-what-the-user-sees--the-complete-flow)

---

## 1. What We Are Building

We are building a **2D top-down driving trial simulator** that lives inside your existing Smart Driving Institute Management System (SDIMS). It is a browser-based game where trainees can practice and take driving trials on a virtual track, just like the real trial ground.

There are **two modes**:

| Mode | What It Simulates |
|------|-------------------|
| **4-Wheeler (Car)** | A full car trial — driving around a track, obeying traffic lights, passing checkpoints in order, and performing reverse parking |
| **2-Wheeler (Bike)** | A motorcycle trial — navigating a narrow balance path, riding a figure-8 pattern, and avoiding traffic cones |

The simulator **scores** the trainee out of 100 points, deducting points for mistakes like hitting boundaries, running red lights, or parking incorrectly. At the end, the result (score, pass/fail, penalty breakdown, time taken) is **saved to your Django database** — exactly like how the written mock test already saves results.

---

## 2. How It Fits Into Your Existing Project

Your project already has 9 Django apps inside the `SDIMS_apps` folder. We are adding a **10th app** called `driving_trial`. This new app follows the exact same patterns as your existing apps:

### What stays the same
- The simulator page extends your existing `base.html` template, so it gets the same sidebar, top bar, theme toggle, and responsive layout that every other page has.
- It uses function-based views with `@login_required` and `@role_required` decorators, just like your other views.
- The model follows the same conventions — `BigAutoField` primary key, `settings.AUTH_USER_MODEL` for the user foreign key, choice tuples for enums, and a `__str__` method.
- Templates are placed flat in the app's `templates/` folder (no subdirectory), matching your existing convention.
- URLs use `app_name = 'driving_trial'` namespace, wired from the main `urls.py` under the path `trial/`.

### What is new
- A `static/simulator/js/` folder is created at the project root to hold all the JavaScript modules. Your project currently has no JS files (everything is inline), but for a game engine with 12+ modules, external files are essential.
- Phaser 3 is loaded from a CDN (a content delivery network — it downloads automatically when the page loads).
- The template uses `<script type="module">` tags, which allow JavaScript files to import from each other cleanly.

### Where the new app sits

```
Your existing project
├── Driving_Institute/          ← Project config (settings, urls)
├── SDIMS_apps/
│   ├── accounts/               ← Already exists
│   ├── courses/                ← Already exists
│   ├── homesandall/            ← Already exists
│   ├── ...7 more apps...
│   └── driving_trial/          ← NEW — our simulator app
├── static/
│   ├── images/                 ← Already exists (logo)
│   └── simulator/              ← NEW — all game JavaScript
│       └── js/
│           ├── main.js
│           ├── scenes/
│           └── modules/
└── templates/
    ├── base.html               ← Already exists (we extend this)
    └── sidebar.html            ← Already exists (we add a link)
```

---

## 3. The Technology Choice — Why Phaser 3

**Phaser 3** is a JavaScript game framework designed specifically for 2D browser games. Here is why it is the right choice for this project:

| Requirement | How Phaser 3 Satisfies It |
|-------------|---------------------------|
| Runs in browser | Phaser renders to an HTML5 Canvas element — no plugins or installations needed |
| Physics collisions | Phaser includes "Arcade Physics" — a built-in lightweight physics engine that handles collisions between objects |
| Smooth movement | Phaser runs a game loop at 60 frames per second, calculating positions every frame for buttery smooth motion |
| Keyboard input | Phaser has a built-in keyboard manager that tracks which keys are pressed right now |
| Django compatible | Phaser runs entirely client-side (in the browser). Django just serves the HTML page. They don't conflict |
| No build tools needed | Phaser can be loaded from a single CDN script tag. No npm, no webpack, no build step |

### What "Arcade Physics" means

Phaser's Arcade Physics is a simple but effective physics system. Every game object can have a "physics body" — an invisible rectangle or circle around it. The physics engine then automatically:
- Detects when two bodies overlap or collide
- Stops objects from passing through each other (if set to collide)
- Applies velocity and acceleration to move objects
- Handles bounce, friction, and drag

We use this for: car-to-wall collisions, car-to-checkpoint overlaps, car-to-traffic-light-zone overlaps, car-to-cone collisions, and parking zone detection.

---

## 4. Overall Architecture

The system has **three layers**:

```
┌─────────────────────────────────────────────────┐
│  LAYER 1: Django (Server Side)                  │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐ │
│  │  Views    │  │  Models   │  │  Templates  │ │
│  │ (serve    │  │ (store    │  │ (HTML page  │ │
│  │  page,    │  │  results  │  │  with Phaser│ │
│  │  save     │  │  in DB)   │  │  canvas)    │ │
│  │  results) │  │           │  │             │ │
│  └───────────┘  └───────────┘  └─────────────┘ │
└─────────────────────┬───────────────────────────┘
                      │ HTTP (page load + API calls)
┌─────────────────────▼───────────────────────────┐
│  LAYER 2: Phaser Game Engine (Client Side)      │
│  ┌──────────────────────────────────────────┐   │
│  │  Scenes (FourWheelerScene / TwoWheeler)  │   │
│  │  - Orchestrates all modules              │   │
│  │  - Runs the game loop                    │   │
│  │  - Handles completion + save             │   │
│  └──────────────────┬───────────────────────┘   │
│                     │ uses                       │
│  ┌──────────────────▼───────────────────────┐   │
│  │  Modules (Vehicle, Track, Scoring, etc.) │   │
│  │  - Each module handles one concern       │   │
│  │  - Modules don't know about each other   │   │
│  │  - The Scene wires them together         │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
                      │ renders to
┌─────────────────────▼───────────────────────────┐
│  LAYER 3: HTML5 Canvas (What the user sees)     │
│  - The track, car, traffic lights, HUD, etc.    │
│  - All drawn at 60 frames per second            │
└─────────────────────────────────────────────────┘
```

### Why "Scenes" and "Modules"?

**Scenes** are Phaser's way of organizing different screens or game modes. Think of them like pages in a website. We have two scenes:
- `FourWheelerScene` — the car trial
- `TwoWheelerScene` — the bike trial

Only one scene runs at a time. When the user picks a mode, we start that scene.

**Modules** are our own JavaScript classes, each responsible for one feature. This is the "modular architecture" you requested. Instead of one giant 2000-line file, we have small, focused files:

| Module | Single Responsibility |
|--------|-----------------------|
| `Vehicle.js` | Car physics and rendering |
| `Bike.js` | Bike physics and rendering |
| `Track.js` | Track boundaries for cars |
| `BikeTrack.js` | Track boundaries for bikes |
| `Scoring.js` | Points and penalties |
| `Checkpoint.js` | Ordered checkpoint system |
| `TrafficLight.js` | Traffic light state machine |
| `ReverseParking.js` | Parking detection |
| `ConeSystem.js` | Cone obstacles for bikes |
| `HUD.js` | On-screen user interface |
| `InputManager.js` | Keyboard input handling |

Each module is a self-contained class. The Scene creates instances of the modules it needs and wires them together. For example, when the Vehicle hits a wall, the Scene tells the Scoring module to deduct points, and tells the HUD module to flash red.

---

## 5. File-by-File Breakdown

### Django Files (Server Side)

#### `SDIMS_apps/driving_trial/__init__.py`
An empty file that tells Python "this folder is a Python package." Every Django app needs one. It contains nothing.

#### `SDIMS_apps/driving_trial/apps.py`
A tiny configuration file that tells Django this app's full name is `SDIMS_apps.driving_trial` and it should use `BigAutoField` for auto-generated primary keys. This follows the exact same pattern as your `license_mocktest/apps.py`.

#### `SDIMS_apps/driving_trial/models.py`
Defines a single database model called `TrialResult`. Every time a trainee completes (or fails) a driving trial, one record is created. It stores:

- **user** — which trainee took the trial (linked to your custom User model)
- **vehicle_type** — "car" or "bike"
- **score** — the final score out of 100
- **result** — "pass" or "fail"
- **pass_mark** — the minimum score needed to pass (default 70)
- **penalties** — a JSON dictionary breaking down exactly what went wrong, like `{"boundary_touch": 3, "red_light": 1, "idle_penalty": 2}`. This uses Django's `JSONField` which stores structured data inside a single database column.
- **completion_time** — how many seconds the trial took
- **taken_at** — the date and time the trial was taken (auto-filled)

This is very similar to your existing `TestAttempt` model in `license_mocktest`, just with driving-specific fields.

#### `SDIMS_apps/driving_trial/views.py`
Contains three view functions:

1. **`simulator`** — Handles a GET request to `/trial/`. Renders the `simulator.html` template which contains the Phaser game canvas. This is the main page.

2. **`save_result`** — Handles a POST request to `/trial/save/`. When the trainee finishes the trial, the JavaScript in the browser sends the results (score, penalties, time, etc.) as JSON data using the `fetch` API. This view receives that data, validates it, creates a `TrialResult` record in the database, and sends back a JSON response confirming success. This is an **API endpoint**, not a regular page — it returns JSON, not HTML.

3. **`trial_history`** — Handles a GET request to `/trial/history/`. Shows a list of past trial attempts for the logged-in user, with scores, pass/fail status, and dates. Similar to the `test_history` view in mocktest.

#### `SDIMS_apps/driving_trial/urls.py`
Maps URL paths to views:
- `/trial/` → `simulator` view
- `/trial/save/` → `save_result` view
- `/trial/history/` → `trial_history` view

Uses `app_name = 'driving_trial'` for namespacing, so other parts of the project can reference these URLs as `'driving_trial:simulator'`, etc.

#### `SDIMS_apps/driving_trial/admin.py`
Registers the `TrialResult` model with Django's admin panel so administrators can view and manage trial results from `/admin/`.

#### `SDIMS_apps/driving_trial/templates/simulator.html`
The main HTML template. This is the most important Django file because it bridges the server and the game. It:

- **Extends `base.html`** — so it gets the sidebar, top bar, and theme system
- **Contains a mode selection area** — two buttons styled to match the SDIMS design system: "4-Wheeler Trial" and "2-Wheeler Trial". The user clicks one to start.
- **Contains a canvas container** — a `<div>` where Phaser will create its game canvas. When idle, it shows instructions about controls (arrow keys, shift for reverse, etc.)
- **Loads Phaser 3 from CDN** — a single `<script>` tag that downloads the Phaser library
- **Loads all JavaScript modules** — using `<script type="module">` tags that load `main.js` and all the modules
- **Passes Django data to JavaScript** — the CSRF token (for security) and the save URL are embedded as `data-*` attributes on a hidden element. The JavaScript reads these when it needs to send results to the server.
- **Contains a results modal** — after the trial ends, a styled overlay shows the final score, pass/fail status, penalty breakdown, and a "Save Results" button.

---

### JavaScript Files (Client Side)

#### `static/simulator/js/main.js`
The **entry point** of the entire game. This file:

1. **Creates the Phaser game configuration** — specifies the canvas size (responsive to the container, default 1200×700), the renderer (auto-detect WebGL or Canvas), and enables Arcade Physics with no gravity (top-down view means no gravity).

2. **Registers both scenes** — adds `FourWheelerScene` and `TwoWheelerScene` to Phaser's scene manager, but doesn't start either yet.

3. **Listens for mode selection** — when the user clicks "4-Wheeler" or "2-Wheeler", it starts the appropriate scene.

4. **Creates the Phaser.Game instance** — this is the master game object. It creates the canvas, initializes the physics engine, and begins the game loop.

#### `static/simulator/js/scenes/FourWheelerScene.js`
The **orchestrator** for the car trial. This is the most complex file because it wires together all the modules. A Phaser scene has three lifecycle methods:

- **`preload()`** — Runs before the scene starts. We don't load any external images (everything is drawn procedurally), so this is minimal.

- **`create()`** — Runs once when the scene starts. This is where all setup happens:
  - Creates the Track (draws the road surface and spawns boundary walls)
  - Creates the Vehicle (the car, positioned at the start line)
  - Creates the Scoring system (initializes at 100 points)
  - Creates the Checkpoints (invisible zones on the track)
  - Creates the Traffic Lights (positioned at intersections)
  - Creates the Reverse Parking zone
  - Creates the HUD (score display, timer, checkpoint progress)
  - Sets up all physics collisions (car ↔ walls, car ↔ checkpoints, car ↔ traffic zones, car ↔ parking zone)
  - Starts the trial timer

- **`update(time, delta)`** — Runs **every single frame** (60 times per second). This is the game loop. Every frame, it:
  - Reads keyboard input
  - Updates vehicle physics (acceleration, steering, friction)
  - Updates traffic light states (cycling through colors)
  - Checks for idle penalty (is the car not moving?)
  - Updates the HUD with current values
  - Checks if trial is complete (all checkpoints passed + parked)

#### `static/simulator/js/scenes/TwoWheelerScene.js`
The orchestrator for the bike trial. Same lifecycle structure as `FourWheelerScene`, but uses `Bike` instead of `Vehicle`, `BikeTrack` instead of `Track`, and `ConeSystem` instead of `ReverseParking`/`TrafficLight`. The bike trial is a different experience — narrower paths, balance mechanics, and cone slalom.

#### `static/simulator/js/modules/Vehicle.js`
The **car physics engine**. This is the heart of the driving feel. It implements realistic top-down vehicle movement, NOT grid-based movement (where you jump from square to square). Here's how the physics work:

**Forward/Backward Movement:**
- The car has a `speed` value (starts at 0)
- Pressing UP adds `acceleration` to `speed` each frame
- Releasing UP causes `speed` to decrease by `friction` each frame (the car coasts to a stop)
- Pressing DOWN applies brakes (stronger deceleration)
- Holding SHIFT enables reverse gear — DOWN then moves backward
- `speed` is capped at `maxSpeed` in both directions

**Steering:**
- The car has a `rotation` angle (the direction it faces)
- Pressing LEFT/RIGHT changes the rotation
- **Crucially, steering only works when the car is moving.** If the car is stopped, pressing left/right does nothing — just like a real car. The faster you go, the more responsive the steering.
- The rotation change is proportional to speed: `rotation += turnRate × (speed / maxSpeed)`

**Position Update:**
- Every frame, the car moves in the direction it's facing by the amount of its speed
- Horizontal movement: `x += cos(rotation) × speed`
- Vertical movement: `y += sin(rotation) × speed`
- This creates smooth, natural car movement with inertia

**Visual Rendering:**
- The car is drawn as a colored rectangle with rounded corners
- A darker strip across the front represents the windshield
- Small yellow rectangles at the front are headlights
- Small red rectangles at the back are taillights
- The car rotates visually to match its physics rotation

#### `static/simulator/js/modules/Bike.js`
Similar to Vehicle but with **motorcycle-specific physics**:

- **Narrower body** — the bike sprite is much thinner than the car
- **Tighter turning radius** — bikes can turn more sharply
- **Balance mechanic** — on narrow paths, if the bike's speed drops below a minimum threshold, it counts as a "foot touch" (the rider put their foot down to balance). This triggers a penalty.
- **No reverse parking** — bikes don't do the parking test
- **Visual rendering** — drawn as a narrow elongated shape with a circular rider silhouette on top

#### `static/simulator/js/modules/Track.js`
Defines the **4-wheeler trial track** — the road layout with boundary walls.

**How the track is built:**
- The track is an oval/L-shaped circuit, similar to a real driving trial ground
- It consists of an **outer boundary** (the outside walls) and an **inner boundary** (the island in the middle)
- Each boundary is made up of multiple rectangular wall segments, placed end-to-end to form the track shape
- The walls are Phaser Arcade Physics "static bodies" — they don't move, but they have collision detection

**Visual elements:**
- The road surface is a dark grey area between the inner and outer walls
- White dashed lines run down the center of the road (lane markings)
- The curbs (edges of the road) are painted with red-and-white striping
- The area outside the track is green (representing grass/ground)
- There's a designated start/finish line

**Collision behavior:**
- When the car's physics body touches a wall's physics body, Phaser detects the collision
- The car's velocity is set to zero (it stops)
- The car bounces back slightly (so it doesn't get stuck inside the wall)
- A penalty event is fired, which the Scene passes to the Scoring module

#### `static/simulator/js/modules/BikeTrack.js`
The **2-wheeler trial track** — very different from the car track:

**Narrow Balance Path:**
- A straight section of road that is only slightly wider than the bike itself
- The trainee must ride through it slowly and steadily without touching the edges
- If the bike touches the boundary walls here, it counts as a "foot touch" penalty
- This tests low-speed control and balance

**Figure-8 Path:**
- Two loops connected at a center crossing point, forming the number 8
- The trainee must navigate the loops smoothly without going outside the lines
- The intersection in the middle tests the ability to transition between turns
- Traffic cones are placed along the edges of the figure-8

**Standard Connecting Sections:**
- Wider road sections connecting the balance path to the figure-8
- These give the rider space to accelerate and prepare

#### `static/simulator/js/modules/Scoring.js`
The **penalty and score manager**. It tracks the trainee's performance throughout the entire trial.

**Starting State:**
- Score begins at **100 points**
- An empty penalty log (a list of every penalty incurred)
- A timer tracking elapsed seconds

**Penalty Types (4-Wheeler):**

| Penalty | Points Deducted | When It Triggers |
|---------|----------------|-------------------|
| Boundary touch | -5 | Car hits a track wall. Has a 1.5-second cooldown so rapidly bouncing off a wall doesn't drain all points instantly |
| Idle too long | -2 per second | Car stays completely stationary for more than 5 seconds. Encourages the trainee to keep moving |
| Red light violation | -15 | Car enters a traffic light zone while the light is red |
| Wrong checkpoint order | -10 | Car reaches checkpoint 3 before passing checkpoint 2, for example |
| Wrong parking angle | -10 | Car parks but is angled more than 15° from the correct orientation |
| Parking line cross | -5 per line | Car's body crosses over one of the parking bay lines |

**Penalty Types (2-Wheeler):**

| Penalty | Points Deducted | When It Triggers |
|---------|----------------|-------------------|
| Boundary touch | -5 | Bike hits track walls |
| Foot touch | -5 | Bike speed drops below threshold on the narrow balance path |
| Cone hit | -5 | Bike collides with a traffic cone on the figure-8 |
| Idle too long | -2 per second | Same as 4-wheeler |

**Cooldowns:**
Each penalty type has a cooldown timer. After a boundary touch penalty, there's a 1.5-second window where another boundary touch won't deduct points. This prevents unfair "stacking" where one mistake cascades into multiple penalties.

**Fail Condition:**
If the score drops below **70** at any point, the trial status changes to "FAIL." The trial doesn't stop immediately — the trainee can continue practicing — but the result is already determined.

**Result Packaging:**
When the trial ends, the Scoring module packages everything into a result object containing the final score, pass/fail status, the complete penalty breakdown (how many of each type), and the total time taken. This is what gets sent to Django.

#### `static/simulator/js/modules/Checkpoint.js`
Implements **ordered checkpoint zones** that the trainee must drive through in sequence.

**What checkpoints are:**
Invisible rectangular zones placed at specific points around the track. The trainee cannot see them directly, but:
- Subtle directional arrows are painted on the road surface showing the correct driving direction
- When the car passes through a checkpoint correctly, a brief green flash animation plays
- The HUD shows progress like "Checkpoint: 3/6"

**Why order matters:**
Real driving trials require you to drive the correct route. You can't skip sections. The checkpoints enforce this:
- Checkpoints are numbered 1 through N (typically 6-8 for the car trial)
- The system tracks which checkpoint number should be reached next
- If you reach checkpoint 1, then 2, then 3 → everything is fine
- If you somehow reach checkpoint 4 without passing checkpoint 3 → a "wrong order" penalty is triggered, and checkpoint 4 doesn't count as passed
- You must go back and pass checkpoint 3 first

**Completion:**
The trial is considered "route complete" when all checkpoints have been passed in order. However, the trial might also require parking (see Reverse Parking), so passing all checkpoints is necessary but not always sufficient.

**Implementation detail:**
Each checkpoint is an Arcade Physics body set to "overlap" mode (not "collide"). This means the car passes through the zone freely — it doesn't stop or bounce. The physics engine just fires an event saying "the car entered this zone," and our Checkpoint module checks if it's the right one in sequence.

#### `static/simulator/js/modules/TrafficLight.js`
Implements **realistic traffic light behavior** with violation detection.

**The State Machine:**
A traffic light cycles through three states in a fixed pattern:

```
GREEN (8 seconds) → YELLOW (3 seconds) → RED (6 seconds) → GREEN ...
```

This runs on a timer independent of the car's position. The lights change whether the car is nearby or not, just like real traffic lights.

**Visual Representation:**
Each traffic light is drawn as:
- A dark rectangular pole/housing
- Three circles stacked vertically (red, yellow, green)
- Only the active color is bright/glowing; the other two are dim/dark grey
- A subtle glow effect around the active light for visibility

**Detection Zone:**
In front of each traffic light, there's an invisible rectangular zone (an Arcade Physics overlap body) representing the stop line area. The zone extends about two car-lengths before the traffic light.

**Violation Logic:**
- If the car **enters** the detection zone while the light is **RED** → violation! -15 points
- If the car is **already inside** the zone when the light **turns red** (it was green/yellow when they entered) → no violation. You can't penalize someone who was already committed to crossing.
- If the light is **YELLOW** → no violation, but it's a warning. The trainee should stop if possible.

**Multiple Instances:**
The track can have multiple traffic lights at different positions (typically 2-3 around the circuit). Each one runs its own independent timer, so they won't all be the same color at the same time. Their timers are staggered with offsets.

#### `static/simulator/js/modules/ReverseParking.js`
Implements **reverse parking detection** — one of the most important skills in a real driving trial.

**The Parking Bay:**
A rectangular parking space is drawn on the track with clear white boundary lines on three sides (left, right, and back). The front is open — this is where the car enters. The bay is sized for the car with moderate clearance on each side.

**Reverse Gear Requirement:**
The trainee must enter the bay in **reverse** (holding the SHIFT key to engage reverse gear). The module checks:
- Is the car moving backward (negative speed)?
- If the car enters the bay moving forward → -10 penalty for not reversing

**Angle Detection:**
Once the car is inside the bay, the module checks the car's rotation angle:
- The parking bay has a "correct angle" (typically 0° or 90° depending on orientation)
- If the car's angle is within ±15° of the correct angle → good parking
- If the angle difference is more than 15° → -10 penalty for incorrect angle
- The visual feedback shows a green highlight for correct angle, orange/red for incorrect

**Line Crossing Detection:**
The module checks if any part of the car's body extends beyond the parking bay boundary lines:
- Left line crossed → -5
- Right line crossed → -5
- Back line crossed → -5
- Each line is checked independently

**Visual Feedback:**
- When the car is outside the bay: the bay lines are white
- When the car enters correctly: the bay area highlights green
- When there's a violation: the specific crossed line flashes red
- When angle is wrong: the bay highlights orange

#### `static/simulator/js/modules/ConeSystem.js`
Traffic cone obstacles used in the **2-wheeler trial only**.

**Placement:**
Orange traffic cones are placed along both sides of the figure-8 path, forming a slalom-like course. They're spaced at regular intervals, creating a channel that the bike must navigate through.

**Physics:**
Each cone is a small Arcade Physics dynamic body (not static). This means:
- The cone has collision detection with the bike
- When the bike hits a cone, the cone gets **knocked aside** — it moves and rotates based on the impact
- This creates a satisfying visual effect and clearly shows the trainee they hit something
- Each knocked cone → -5 penalty

**Why dynamic instead of static:**
Static bodies don't move on collision. If cones were static, hitting one would feel like hitting a wall. By making them dynamic, they behave like real lightweight cones — they get pushed around. The bike still passes through (with a slight speed reduction) rather than coming to a complete stop.

#### `static/simulator/js/modules/HUD.js`
The **heads-up display** — all the information shown on screen during the trial.

**Elements displayed:**

| Element | Location | Description |
|---------|----------|-------------|
| Score | Top-left | Current points out of 100. Flashes red briefly when points are deducted |
| Timer | Top-left, below score | Elapsed time in MM:SS format |
| Checkpoint progress | Top-right | Shows "Checkpoint: 3/6" — how many have been passed |
| Gear indicator | Bottom-left | Shows "D" for drive or "R" for reverse. Changes color in reverse |
| Speed bar | Bottom-left, next to gear | A small bar showing current speed relative to max speed |
| Penalty feed | Bottom-right | The last 3 penalties, like a log: "⚠ Boundary touch -5" with a fade-out animation |
| Mini-instructions | Top-center | Small text: "↑↓ Accelerate/Brake • ←→ Steer • SHIFT Reverse" |

**Fail Screen:**
When the score drops below 70, a semi-transparent dark overlay appears with large red "TRIAL FAILED" text, the final score, and options to retry or go back.

**Completion Screen:**
When all checkpoints are passed (and parking completed for 4-wheeler), a completion overlay appears with:
- Final score in large text
- "PASSED" in green or "FAILED" in red
- Penalty breakdown table
- Time taken
- "Save Results" button (sends data to Django)
- "Try Again" button

#### `static/simulator/js/modules/InputManager.js`
A thin wrapper around Phaser's keyboard system. It provides clean methods like:
- `isAccelerating()` — is the UP arrow pressed?
- `isBraking()` — is the DOWN arrow pressed?
- `isSteeringLeft()` — is the LEFT arrow pressed?
- `isSteeringRight()` — is the RIGHT arrow pressed?
- `isReversing()` — is the SHIFT key held?
- `isHandbraking()` — is the SPACE key pressed?

**Why a separate module?**
It abstracts away Phaser's specific keyboard API. If we ever want to add gamepad support, touch controls, or remap keys, we only change this one file instead of every file that checks for input.

---

## 6. Prompt 1 — Phaser Setup & Car Movement

This prompt establishes the foundation. When complete, the user sees:
- A dark canvas embedded in the SDIMS page (with sidebar and top bar visible)
- A car sprite centered on screen
- Pressing arrow keys moves the car with smooth acceleration
- The car steers realistically — it turns in arcs, not sharp 90° snaps
- Releasing keys causes the car to coast and gradually stop
- The car rotates visually to match its direction of travel

**What "realistic top-down movement" means in practice:**
Imagine looking at a car from directly above (like a drone camera). When you turn the steering wheel, the car doesn't instantly face a new direction — it carves an arc. The faster you go, the wider the arc. When stopped, turning the wheel does nothing to your position. This is what we replicate. Grid movement (Pac-Man style, where you snap between squares) would feel completely wrong for a driving simulator.

---

## 7. Prompt 2 — Track Boundaries

Building on Prompt 1, this adds:
- A visible trial track — a road with inner and outer walls
- The road has lane markings and curb painting
- The area outside the track is grass-colored
- If the car drives into a wall, it stops (doesn't pass through)
- The car rebounds slightly so it doesn't get stuck inside the wall geometry

**The track layout** is designed to resemble a simplified real-world trial ground:
- A roughly rectangular circuit with rounded corners
- Wide enough for comfortable driving but narrow enough to require careful steering
- At least one sharp turn to test control
- A straight section leading to the parking bay
- Intersections where traffic lights will be placed

---

## 8. Prompt 3 — Scoring System

Building on Prompts 1-2, this adds:
- A visible score counter starting at 100
- Points deducted when the car hits walls (-5 per hit with cooldown)
- Points deducted when the car sits idle too long (-2 per second after 5 seconds)
- All penalties logged with timestamps
- A penalty feed in the corner showing recent deductions
- A fail overlay when score drops below 70

The scoring system is designed to be **fair but demanding** — mirroring real driving trials where minor mistakes are penalized but don't end the test, while major or repeated errors lead to failure.

---

## 9. Prompt 4 — Checkpoints

Building on Prompts 1-3, this adds:
- 6-8 invisible checkpoint zones placed around the track
- Subtle arrows painted on the road showing the correct direction
- Checkpoints must be passed in order (1 → 2 → 3 → ...)
- Green flash animation when a checkpoint is correctly passed
- HUD shows "Checkpoint: 3/6" progress
- Skipping a checkpoint triggers a -10 penalty
- All checkpoints must be passed to complete the trial

---

## 10. Prompt 5 — Traffic Lights

Building on Prompts 1-4, this adds:
- 2-3 traffic lights placed at intersections on the track
- Each light cycles: Green (8s) → Yellow (3s) → Red (6s)
- Visual traffic light rendered with glowing active color
- Running a red light deducts 15 points
- Entering on green/yellow and passing through during red is NOT penalized (the "committed crossing" rule)
- Traffic lights are staggered so they're not all the same color simultaneously

---

## 11. Prompt 6 — Reverse Parking

Building on Prompts 1-5, this adds:
- A marked parking bay on the track
- The car must enter in reverse gear (SHIFT key held)
- Forward entry → -10 penalty
- Parking angle more than 15° off → -10 penalty
- Crossing bay lines → -5 per line
- Visual feedback: green for correct, red for violations
- Parking completion is required to finish the 4-wheeler trial

---

## 12. Prompt 7 — Django Backend Integration

Building on Prompts 1-6, this adds the **server-side connection**:

**The Save Flow:**
1. Trainee completes the trial (or fails)
2. The completion screen shows results with a "Save Results" button
3. Clicking "Save" triggers a JavaScript `fetch()` call
4. The fetch sends a POST request to `/trial/save/` with JSON data containing: score, pass/fail, vehicle type, penalty breakdown, and completion time
5. The request includes the CSRF token (extracted from the Django template) in the headers for security
6. Django's view receives the data, validates it, and creates a `TrialResult` database record
7. Django sends back a JSON response: `{"status": "success", "id": 42}`
8. The JavaScript shows a "Saved successfully" confirmation
9. The trainee can view their history at `/trial/history/`

**Why `fetch()` instead of a form submission:**
A normal HTML form submission would reload the entire page, destroying the Phaser game state. Using `fetch()` (an AJAX call) sends the data in the background without leaving the page. The user stays on the same screen and sees a confirmation message.

---

## 13. Prompt 8 — Two-Wheeler Mode

This is a **completely separate game mode** with its own scene, vehicle, and track:

**How it differs from the car trial:**

| Aspect | 4-Wheeler | 2-Wheeler |
|--------|-----------|-----------|
| Vehicle | Wide car | Narrow motorcycle |
| Track | Oval circuit with intersections | Narrow path + figure-8 |
| Traffic lights | Yes (2-3 on circuit) | No |
| Reverse parking | Yes (parking bay) | No |
| Checkpoints | Yes (6-8 around circuit) | Yes (along path and figure-8) |
| Cones | No | Yes (along figure-8 edges) |
| Balance test | No | Yes (narrow path with foot-touch penalty) |
| Scoring | Same base system | Same base system + bike-specific penalties |

**The balance mechanic:**
On the narrow balance path section, the bike must maintain a minimum speed. In real life, a motorcycle at very low speed becomes unstable and the rider puts a foot down. We simulate this: if the bike speed drops below a threshold while on the narrow path, a "foot touch" penalty is triggered (-5 points). This encourages smooth, controlled riding rather than crawling.

**The figure-8:**
Two loops of approximately equal size connected at a center point. The trainee enters one loop, completes it, passes through the center, completes the second loop, and exits. Cones line both sides. The challenge is maintaining smooth transitions between the clockwise and counterclockwise turns.

---

## 14. How All Modules Connect Together

Here is the flow of communication between modules during gameplay. The **Scene** is always the middleman — modules never talk to each other directly.

```
User presses UP arrow
    → InputManager detects it
    → Scene reads InputManager in update()
    → Scene tells Vehicle to accelerate
    → Vehicle updates its position
    → Physics engine detects Vehicle overlaps Checkpoint 3
    → Scene receives the overlap callback
    → Scene tells Checkpoint module "zone 3 was entered"
    → Checkpoint module checks: is 3 the next expected? Yes!
    → Checkpoint module marks 3 as passed
    → Scene tells HUD to update checkpoint display to "3/6"
    → Scene tells HUD to flash green at checkpoint location
```

Another example — a wall collision:

```
Vehicle moves forward
    → Physics engine detects Vehicle collides with Wall
    → Scene receives the collision callback
    → Scene tells Vehicle to stop (velocity = 0)
    → Scene tells Scoring to deduct 5 points for "boundary_touch"
    → Scoring checks cooldown: has 1.5s passed since last boundary penalty?
        → Yes: deduct 5 points, record penalty, reset cooldown
        → No: ignore (already penalized recently)
    → Scene tells HUD to update score display
    → Scene tells HUD to show penalty in feed: "⚠ Boundary touch -5"
```

This architecture means:
- **Vehicle doesn't know about scoring** — it just drives
- **Scoring doesn't know about the track** — it just manages numbers
- **HUD doesn't know about physics** — it just displays information
- **The Scene knows about everything** and coordinates between them

This is clean separation of concerns. If you want to change how scoring works, you only touch `Scoring.js`. If you want a different track layout, you only touch `Track.js`. Nothing else breaks.

---

## 15. The Game Loop — What Happens Every Frame

Phaser calls the scene's `update()` method approximately **60 times per second**. Here's what happens in each call, in order:

```
1. READ INPUT
   - Check which keys are currently pressed
   - Determine intent: accelerating? braking? steering? reversing?

2. UPDATE VEHICLE PHYSICS
   - Apply acceleration or friction based on input
   - Apply steering rotation based on input and current speed
   - Calculate new position based on speed and rotation
   - Move the vehicle sprite to the new position
   - Rotate the vehicle sprite to match

3. PHYSICS ENGINE (automatic)
   - Phaser checks all physics bodies for collisions and overlaps
   - Fires callbacks for any interactions detected

4. UPDATE TRAFFIC LIGHTS
   - Check each traffic light's timer
   - If enough time has passed, transition to next state
   - Update visual appearance (which circle is lit)

5. CHECK IDLE PENALTY
   - If vehicle speed is near zero, increment idle timer
   - If idle timer exceeds 5 seconds, deduct 2 points per second
   - If vehicle is moving, reset idle timer

6. UPDATE HUD
   - Refresh score display
   - Refresh timer display
   - Refresh checkpoint progress
   - Refresh gear indicator
   - Refresh speed bar
   - Animate any pending penalty notifications

7. CHECK COMPLETION
   - Are all checkpoints passed?
   - Is parking completed (4-wheeler)?
   - If both: trigger trial completion sequence
```

Each of these steps takes a tiny fraction of a millisecond. At 60fps, each frame has about 16.7ms to complete. Our logic uses well under 1ms, so the game runs smoothly.

---

## 16. Security & CSRF Handling

Django has built-in **Cross-Site Request Forgery (CSRF) protection**. Every POST request to Django must include a CSRF token — a secret value that proves the request came from a legitimate page on your site, not from a malicious third-party site.

**How we handle this for the game's save functionality:**

1. In the Django template (`simulator.html`), we use Django's `{% csrf_token %}` template tag to embed the token in the page.

2. We store the token value in a JavaScript-accessible location (a `data-csrf` attribute on a hidden element, or by reading the `csrftoken` cookie).

3. When the JavaScript makes a `fetch()` POST request to save results, it includes the CSRF token in the request headers as `X-CSRFToken`.

4. Django's CSRF middleware validates the token. If it's valid, the request proceeds. If not, Django returns a 403 Forbidden error.

This is the same mechanism your existing mocktest uses when submitting the form — we're just doing it via JavaScript instead of an HTML form.

---

## 17. What the User Sees — The Complete Flow

Here's the trainee's experience from start to finish:

### Step 1: Navigate
The trainee logs in and clicks "Driving Trial" in the sidebar. They arrive at `/trial/`.

### Step 2: Choose Mode
They see a clean, styled page matching the SDIMS design. Two large buttons:
- 🚗 **4-Wheeler Trial** — "Test your car driving skills on the trial circuit"
- 🏍️ **2-Wheeler Trial** — "Navigate the balance path and figure-8 course"

Below the buttons, a quick-reference card shows the controls.

### Step 3: Start Trial
They click a mode button. The selection UI fades out and the Phaser canvas fills the content area. The track appears with the vehicle at the start position. A brief 3-second countdown: "3... 2... 1... GO!"

### Step 4: Drive
The trainee drives using arrow keys. The HUD shows their score (100), timer (00:00), checkpoint progress (0/6), and gear (D).

They navigate the track, passing checkpoints (green flashes, progress updates), obeying traffic lights (watching for red), and eventually reaching the parking bay.

If they make mistakes:
- Hit a wall → car stops, score drops to 95, penalty feed shows "⚠ Boundary touch -5"
- Run a red light → score drops to 80, penalty feed shows "⚠ Red light violation -15"
- Sit idle → score gradually decreases, penalty feed shows "⚠ Idle penalty -2"

### Step 5: Complete (or Fail)
If all checkpoints are passed and parking is done: the completion screen appears with final results.
If score drops below 70: the fail screen appears, but they can continue for practice.

### Step 6: Save Results
They click "Save Results." The data goes to Django. A confirmation appears: "Results saved successfully!" The result is now in the database and visible in trial history.

### Step 7: History
They can visit `/trial/history/` to see all past attempts — scores, dates, pass/fail status — in a table styled like the existing test history page.

---

> [!TIP]
> **Ready to build?** Once you approve the implementation plan, I'll start creating all these files. The implementation follows the build order: Prompt 1 first (get the car moving), then Prompt 2 (add walls), and so on — each building on the last. But all files will be created together since the architecture is designed upfront.
