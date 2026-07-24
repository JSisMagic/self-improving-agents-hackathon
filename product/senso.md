I want to set up Senso so you can search my company's documents. My API key is: SENSO_API_KEY in the .env file

Please do the following:

Install the Senso CLI: `npm install -g @senso-ai/cli`
Set my API key as an environment variable: export SENSO_API_KEY="tgr_W1kLxQS8uZLQOVmB_MPkMjxji7_45cnf0rdu165AeVU"
Install the Senso onboarding skill: `npx @senso-ai/shipables install senso-ai/senso-onboarding`
Start a fresh agent session so the newly installed skill is discoverable
Verify everything works: senso whoami
Verify org details are readable: senso org get

Once setup is confirmed in the fresh session, run the onboarding skill. It will pull the company website from existing org settings when available, research the company, populate the knowledge base, configure the brand kit and content types, generate drafts, publish sample citeables, and kick off GEO monitoring — all automatically. No need to upload a document manually first.