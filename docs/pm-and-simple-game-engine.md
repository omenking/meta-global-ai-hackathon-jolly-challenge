## Project Manager and Simple Game Engine

So we two things:
- a simple game engine that is determinstic, with session replay and logging
- a project manager so we can use feature driven development and test each feature as a human before merged into main.

We just rolled our own task manager/project manager using markdownfiles and SQLITE db.

I wanted to have features define in a specific template.
We will drive feature development from Muse Code interactive
We will let the agent handle the tasks, but we as the human stay focused on the high level features.

We made sure to have Test Levels so we can throughly test mechanics in isolate, and we expect the agent to add screenshots, save reply sessions, and allow to clearly inspect their work as well they have the tools to debug their issues.
![](../scratchpad/pm-001.png)
![](../scratchpad/pm-002.png)
![](../scratchpad/pm-003.png)

The UI was becoming an issues so we looked for a component UI and added HeroUI

I rediscovered that muse-wonder-1.0 is avaible as an API and so I have started using wonder more generously. This would have save us so much trouble if I realized this sooner.

As using Spark was not efficent in many cases for UI development.

## Big Open Question

Should we allow feature development and task development to be driven by Spark or Wonder? We currently use Wonder medium - xhigh.


## UX Issues

When we got to implement the replay feature, Wonder was struggling with the UX.
I figured it time we try using https://www.skills.sh

I tried using HeroUI and the GUI for debugging called lava.
It just struggles to make a usable.

I ask ChatGPT to identify skills and give me prompt:

```sh
Use the interface-design and ux-usability-foundations skills to redesign the existing game replay/session debugging interface.This is an operator tool, not a marketing dashboard, settings panel, or Leva-style parameter editor.Primary workflows: select a recorded session, replay or pause it, scrub and step through events, inspect state at the selected step, annotate a step, and fork from that step.First analyze the existing screenshots and component structure. Propose the information architecture before making code changes.Requirements:- Preserve an unobstructed game viewport.
- Use one unified playback timeline and control bar.
- Keep a compact, readable step inspector beside the game.
- Make the current session, step, playback state, and available actions obvious.
- Hide infrequently used filtering and diagnostics until needed.
- Preserve existing replay functionality and keyboard usability.
- Inspect actual browser screenshots and critique the result before finishing.
```

Maybe should make finding skills and using them part of our workflow:

https://www.skills.sh/vercel-labs/skills/find-skills

## Feature Development Workflow

The PM tool did seem useful but the workflow of going to the interative Muse Code and the editor made it less likely to communicate within the PM tool.

I guess other platforms eg. Github would have hook on comments and they would reply that way.

So we should consider in the future testing another PM system or a simpler system since we never had blockers,
and we had single task execution at a time. We orginally thought this would be driven by subagent development with parellel tasks,
but the code setup one to drive one by one. This isn't a bad idea since we could do human review at each step.

Honestly its probably for the best but our PM tool could be simpler.

### Feature Development Findings

We were able to develop our features:
- Game shell and deterministic core
- Player movement and collision
- Session logs, replay and forks
- Level timer and restart
- Keys and locks
- Orbs and gate
- Warp and level progression
- HUD: timer, orbs, level and inventory

Some tasks depended on other, we didn't do a full test on all features together in a level, but I noticed going back to other test levels the AI seem to have implemented the features that they were reliant on so I am confident the base game works.

## Next Steps

Something I didn't consider was how the code should be organized.
I was wondering if the tasks would be more cost effective depending how the code organized.
I looked at the code and its just large monolothic files.

1. I think we should **refactor the code to use a known way of organizing game code eg.  Classic OOP Inheritance, Component Based, or  Entity Component System (ECS)
2. We should really treat novetely features like a mod system. We can retoactively go and change keys and locks in that system.
  - even though we are the only modding the game, I think that isolating the novetly system on the base game will cost less for implementation for AI or at least crawl through less files.
3. We need to decide the size of levels. and actual scale of levels screen on screen. Right now all levels fit the entire viewport but in chip's challenge levels are large enough that you have parallax scrolling so basically a camera system.

I talked to Muse Wonder outside of our spend budget in playground and so I have a new plan for us to iterate on.

## Feature Development Obstacles

We really struggled with creating GUI elements. I ended up just generating partial assets in Muse Playground and completing the rest of work in Illustrator and Photoshop.

Our Asset Design Tool is still cumbersome to use. I could see an iteration where its more like a chatbot like in Muse Playground, And we really should have Muse Wonder generating optimal prompts.

GUI's are hard because of where they need to be spliced, so I'm not sure how Muse Wonder or any system can handle that.

Until we added skills.sh we really stuggled with getting Muse Wonder to produce usable GUIs.

We could consider using more skills, but we haven't experienced any other painpoints, or simply haven't considered more skills.

Feature development looked mostly like $5 to $10 per feature.

In terms of development for this kind of game, its hard to say if its justified.
There probably is a more optiminal way to build features, but I think it requires a stronger coding, skill knowledge foundational when building games with AI.

