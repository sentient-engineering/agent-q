# agentq - advanced reasoning and learning for autonomous AI agents

agentq implementation

### demo

checkout this [loom video](https://www.loom.com/share/2037ee751b4f491c8d2ffd472d8223bd?sid=53d08a9f-5a9b-4388-ae69-445032b31738) for a quick demo

### agentq and agentq

you might notice two separate implementations of agentq in the repo. `agentq` folder contains a simpler approach to implementing multi-agent conversation required between a planner and a browser agent.

the `agentq` folder contains another approach based on [finite state machines](https://github.com/sentient-engineering/multi-agent-fsm). there are slight nuances and both result in similar level or performace. however, the fsm approach is more scalable, and we will be doing further improvements in it.

the downside of fsm agent is that it is dependent on [structured output](https://openai.com/index/introducing-structured-outputs-in-the-api/) from open ai. so you can't reliably use cheaper models like gpt4o-mini or other oss models which is possible in `agentq`

### setup

1. we recommend installing poetry before proceeding with the next steps. you can install poetry using these [instructions](https://python-poetry.org/docs/#installation)

2. install dependencies

```bash
poetry install
```

3. start chrome in dev mode - in a seaparate terminal, use the command to start a chrome instance and do necesssary logins to job websites like linkedin/ wellfound, etc.

for mac, use command -

```bash
sudo /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

for linux -

```bash
google-chrome --remote-debugging-port=9222
```

for windows -

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

4. set up env - add openai and [langsmith](https://smith.langchain.com) keys to .env file. you can refer .env.example. currently adding langsmith is required but if you do not want to use it for tracing - then you can comment the line `litellm.success_callback = ["langsmith"]` in the `./agentq/core/agent/base.py` file.

5. run the agent

```bash
python -u -m agentq
```

### Run evals

```bash
 python -m test.tests_processor --orchestrator_type fsm
```

#### citations

a bunch of amazing work in the space has inspired this.

```
@misc{putta2024agentqadvancedreasoning,
      title={Agent Q: Advanced Reasoning and Learning for Autonomous AI Agents},
      author={Pranav Putta and Edmund Mills and Naman Garg and Sumeet Motwani and Chelsea Finn and Divyansh Garg and Rafael Rafailov},
      year={2024},
      eprint={2408.07199},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2408.07199},
}
```

```
@article{he2024webvoyager,
  title={WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models},
  author={He, Hongliang and Yao, Wenlin and Ma, Kaixin and Yu, Wenhao and Dai, Yong and Zhang, Hongming and Lan, Zhenzhong and Yu, Dong},
  journal={arXiv preprint arXiv:2401.13919},
  year={2024}
}
```

```
@misc{abuelsaad2024-agente,
      title={Agent-E: From Autonomous Web Navigation to Foundational Design Principles in Agentic Systems},
      author={Tamer Abuelsaad and Deepak Akkil and Prasenjit Dey and Ashish Jagmohan and Aditya Vempaty and Ravi Kokku},
      year={2024},
      eprint={2407.13032},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2407.13032},
}
```
