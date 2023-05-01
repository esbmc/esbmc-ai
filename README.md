# ESBMC AI

AI Augmented ESBMC processing. Passes the output from ESBMC to an AI model that allows the user to use
natural language to understand the output. As the output from ESBMC can be quite technical in nature.
The AI can also be asked other questions, such as suggestions on how to fix the problem outputted by ESBMC,
and to offer further explanations.

This is an area of research. From the ESBMC GitHub:

> The efficient SMT-based context-bounded model checker (ESBMC)

[demo.webm](https://user-images.githubusercontent.com/9535618/235352993-b54c47ef-a1c6-422c-aa5b-07edc2988521.webm)

## Initial Setup

1. Install required Python modules: `pip install -r requirements.txt`. NB: If it doesn't work then try pip3 - depending on the python version on the OS.
2. ESBMC-AI does not come with the original ESBMC software. In order to use ESBMC-AI you must provide ESBMC. Download [ESBMC](http://esbmc.org/) executable or build from [source](https://github.com/esbmc/esbmc).
3. Create a .env file using the provided .env.example as a template, and, insert your OpenAI API key.
4. Enter the ESBMC executable location in the .env `ESBMC_PATH`.
5. Further adjust .env settings as required.
6. You can now run ESBMC-AI.

## Settings

The following settings are adjustable in the .env file. **Some settings are allowed to be omitted, however, the
program will display a warning when done so as it is not recommended**. This list may be incomplete:

1. `OPENAI_API_KEY`: Your OpenAI API key.
2. `CHAT_TEMPERATURE`: The temperature parameter used when calling the chat completion API. This controls the temperature sampling that the model uses. Higher values like 0.8 and above will make the output more random, on the other hand, lower values like 0.2 will be more deterministic. **Allowed values are between 0.0 to 2.0**. Default is 1.0.
3. `AI_MODEL`: The model to use. Options: `gpt-3.5-turbo`, `gpt-4` (under API key conditions).
4. `ESBMC_PATH`: Override the default ESBMC path. Leave blank to use the default ("./esbmc").
5. `CFG_SYS_PATH`: Path to JSON file that contains initial prompt messages for the AI model that give it instructions on how to function.
6. `CFG_INITIAL_PROMPT_PATH`: Text file that contains the instructions to initiate the initial prompt, where the AI is asked to walk through the code and explain the ESBMC output.

## Usage

### Basic

```bash
./main.py /path/to/source_code.c
```

### Help

```bash
./main.py -h
```

### In-Chat Commands Help

```
/help
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Acknowledgments

- [ESBMC](https://github.com/esbmc/esbmc)
- [OpenAI Chat API](https://platform.openai.com/docs/guides/chat)

## License

[GNU Affero General Public License v3.0](https://github.com/Yiannis128/esbmc-ai/blob/master/LICENSE)
