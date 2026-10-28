# Minimal Graphically Assets

These are the graphics at minumum that we need in order to build our Chip's Challenge clone.

The game graphics is tile-based.
We will use a higher resolution tile eg. 512x512. All game assets minus the UI fit these graphics.

## Floor Tiles
- default ground tile
- information tile (when walked over provides tool tip)

## Wall Tiles
- default wall tile
- wall tile with coloured a lock
  - red, blue, green, yellow

## Objects
- key
  - red
  - blue
  - green
  - yellow
- orb (basically our chips)
- gate (blocks the elevator)
- portal (our elevator tile that takes us to the next level)
- Jolly (the character that moves around)

## Muse Image 1.0 Generation Script

Muse Code does not currently have direct access to Muse Image 1.0

So we will need to drive our use of Muse Image 1.0 through a local script tha Muse Code can use.

Our prompt to create the script:
```sh
We want an executable script that can let generate images using Muse Image 1.0

It should load the META_API_KEY using meta-keyguard get so we can track our usage for costcenter.

We want to be able to set:
- the ratio / dimensions
- provide an image prompt
- provide the output path
- be able to supply images to the prompt for reference

We can use the OpenAI SDK as Muse Model API is compatible and does not have its own SDK. Create script in scripts/gen-image
```

Test Example of gen image:
```sh
scripts/gen-image -p "Top-down 2D puzzle-game floor tile, light gray stone with su
btle texture, flat clean game-art style, single square tile filling the frame, no char
acters, no text" 
--ratio 1:1 
-o assets/tiles/floor-default.png
```

Follow up prompt to fix the script:
``sh
Some problems:
- I want to supply the prompt via a file directory
- I don't see dimensions.
```

So new output:

```sh
scripts/gen-image \
--width 512 --height 512 \
--prompt-file scratchpad/testgenimage/floor.md \
-o scratchpad/testgenimage/default.png
```

Our script works, but we will need to consideration basic optimization with tilesets, so its possible we will need generate all tiles and create a single unified image.

This is an issue for later when we decide what game engine we are using.

## Asset Output Generation

I want to make sure we can iterate on our generated images. So we simply don't want to use just use the image generation script directly.

We do know we want to have versioned prompts.

So maybe we have an assets directory with our prompts and each asset will have its own folder, and we will manually name our prompt files.

`/assets/prompts/default-floor/init`

This will produce an outputed file:
`/assets/outputs/default-floor-init-[hash]`

The reason we have a hash is because the file could be generated multiple times.
The hash just be the unix iso timestamp.

We will want a new script to drive the assets.
```sh
gen-assets \
  --manifest-file assets/manifest.yml \
  --judgements-file assets/judgements.yml 
```

Now updating the manifest file and judgements file will be tedious.

When we use Meta Playground Muse Image we can have a conversation to iterate on our image. But we don't capture those iterations, and they don't start from an fresh instance on each iteration.

We also don't store the "judgement" which is used for improving the the image prompts.

So what I want is a UI:
I can add an assets: eg. default_floor
I can add versioned prompts
A version prompted takes the following:
- a previous prompt:
  - which will carry forward the image, and judgement
  - it will load the previous prompt into our new prompt.
    - I can tweak the prompt
After an image is generated Im expeceted to provide human review aka judgement.

We use Muse to create the plan: `plans/iterative-asset-design-tool.md`

It generated out a new folder and to our tool:

```sh
source .venv/bin/activate
pip install -r requirements.txt
python tools/server.py
```

I am using Claude/OpenAI to iterate on Muse Cost Center just because I want to keep my Meta spend very clean for this project. It picked up indirectly something Meta's script on medium missed out on. 
> One thing to check: the PNG is 1600×1600, even though you asked for 512×512 and the script's summary line says size=512x512. Either the API ignores the requested size for this model, or gen-image isn't passing --width/--height through correctly. This doesn't change the cost (pricing is per image), but you may not be getting the size you expect. I can look into it if you want.

We will correct the gen-image to resize, but save original asset.

```sh
scripts/gen-image \
--width 512 --height 512 \
--prompt-file scratchpad/testgenimage/floor.md \
-o scratchpad/testgenimage/default.png
```

We made a new plan to fix the gen image generation: `plans/fix-gen-image-script.md`

We will need ffmpeg on our WSL machine
```sh
sudo apt update
sudo apt install -y ffmpeg
```

