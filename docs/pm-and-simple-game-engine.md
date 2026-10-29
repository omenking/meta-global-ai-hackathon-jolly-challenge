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
