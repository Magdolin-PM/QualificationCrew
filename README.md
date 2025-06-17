# Qualification Crew

CrewAI and Langchain 
Coordination between agents that are tasked with enrichment, lead qualification and lead scoring (deterministic algorithm), prioritization of leads.

## Installation

Ensure you have Python >=3.10 <=3.13 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

1. First lock the dependencies and then install them:
```bash
uv lock
```
```bash
uv sync
```
### Customizing

**Add your `OPENAI_API_KEY` into the `.env` file**

- Modify `src/crewai_plus_lead_scoring/config/agents.yaml` to define your agents
- Modify `src/crewai_plus_lead_scoring/config/tasks.yaml` to define your tasks
- Modify `src/crewai_plus_lead_scoring/crew.py` to add your own logic, tools and specific args
- Modify `src/crewai_plus_lead_scoring/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
uv run crewai_plus_lead_scoring
```

This command initializes the crewai-plus-lead-scoring Crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folser

## Understanding Your Crew

The crewai-plus-lead-scoring Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

