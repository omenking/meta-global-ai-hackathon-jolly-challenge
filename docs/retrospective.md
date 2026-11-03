# Retrospective

## What did I build?
A Jolly-verse clone of 1989's Chip's Challenge.

## Did I finish?
No, I have playable test levels, but not a polished game.

## Were there any limitations or constraints?

### $150 Limit
I self imposed that I would only spend $150 USD in  Meta Model API

$150 got me to the base game engine.
$150 to implement at scale the 73 features.

### Only Meta Model API
That I would *restrict myself to just Meta models. Spark, Wonder, Image.

I did use Claude and Codex for some routine tasks,
for Muse CostCenter and some summary information but
not for building the game or its tools.

## How did you track your Meta usage?
I built a tool called Meta CostCenter the day before the Hackathon.
I could track Muse Code or instrument any code to capture in the Meta Cost Center.

## Did you gain any Meta Models or AI Workload specific knowledge?
Yes.

### Muse Spark vs Muse Wonder Efforts

Muse Spark at Xhigh struggled to create good GUI and Web UI.
Muse Wonder low and medium was very cost effective and good at building GUI and Web UI
but only if you supplied it a good Agent SKill eg. skills.sh

Since Muse Wonder is positioned as a long-horizon model you'd expect it to
be expensive but the low effort range has become the main driver for routine tasks.

Muse Spark is much more suited to be used as an atomized task within a chain of agentic calls in an agentic workload.

### Coding Factory

I unintentially built a coding factory.
This started with building a simple Project Management tool to manage features and tasks.

### Muse Image 1.0
- Don't single shot, but give Muse several images references of what is correct or no correct.
- Since Muse Image 1.0 is cost effective at 1 cent, you might as well generate 10 images and then carry those forward with comments to improve iterations
- Iterative approach produces excellent results
- Writing manual prompts results in Muse Image 1.0 being too literal in generation
- Use Muse Wonder low to generate prompt images.

I did try to build an agentic loop that would iterate on assets but it failed.

I could not create the assets I needed for my 73 features.

Muse had a really hard time generating a walk cycle frame per frame.

I tried 3d image reference, marking up the image, trying to generate a sprite sheet or manually driving edits on single frames.

### Gating

Depsite having clear instructions Wonder failed to follow my test instructions.
By adding a gate to the states of my Project Management tool I could get it properly
test the game.