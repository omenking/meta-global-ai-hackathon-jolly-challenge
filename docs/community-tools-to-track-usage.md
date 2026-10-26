# Community Tools ot Track Usage 

I created two community tools to track usage and safeguard my API keys before the start of the Hackathon.
- https://github.com/omenking/meta-costcenter
- https://github.com/omenking/meta-keyguard

I want to capture all of the my usage data.
I want to have kill switch that will stop if I hit $150 in this project.

> These tools have only been tested Windows WSL Ubuntu.

## Setup
We will fully make sure we are setup for our usage costs.

Install Meta Cost Center:
```sh
curl -fsSL https://raw.githubusercontent.com/omenking/meta-costcenter/main/install.sh | sh
```

Check if it works:
```sh
meta-cost doctor
```
Launch the UI:
```sh
meta-cost show
```

Install Meta keyguard:
```sh
curl -fsSL https://raw.githubusercontent.com/omenking/meta-keyguard/main/install.sh | sh
```

Install the bridge:
```sh
meta-keyguard install-bridge
```

> This will dump a Chrome extension into the chrome extension folder. its not enough to load it into your native chrome.

- Go to chrome://extensions
- Click the Update button
- Click the Load Unpack
- Add the chrome extension, when you ran the bridge it told it where it loaded it from.

```sh
meta-keyguard doctor
```

Make sure you get full passes.


## Create your token

```sh
meta-keyguard config set max_ttl 10d
meta-keyguard create jolly-challenge --ttl 10d
meta-keyguard list
```

## Ensure Cross Integration Turned On

```sh
meta-keyguard cost-center on
```
> now cost-center can destroy keys if billing limit is reached.

Check for cross integration keys.
```sh
meta-keyguard cost-center check
```



## Install Muse Hook
Muse Code won't by default track spend between sub and API eg. PAYG, so we add hook to ensure that information is collected.

```sh
meta-cost hook install      
meta-cost hook status  
```

```sh
meta-cost alert set --monthly-usd 150 --project meta-global-ai-hackathon-jolly-challenge --revoke-keys 'jolly-challenge'
```

Check the alert is there.

## Do a sanity check

Using muse-spark 1.3
```sh
muse
```