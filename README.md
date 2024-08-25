# agentq - advanced reasoning and learning for autonomous AI agents

agentq implementation code

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

4. set up env - add openai and [langfuse](https://langfuse.com) keys to .env file. you can refer .env.example. currently adding langfuse is required. If you do not want tracing - then you can do the following changes

   - directly import open ai client via `import openai` rather than `from langfuse.openai import openai` in the `./agentq/core/agent/base.py` file.
   - you would also have to comment out the @obseve decorator and the below piece of code from the `run` function in the same file

   ```python
   langfuse_context.update_current_trace(
               name=self.agnet_name,
               session_id=session_id
         )
   ```

5. run the agent

```bash
python -u -m agentq
```

### run evals

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
