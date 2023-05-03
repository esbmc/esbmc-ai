# ESBMC AI

AI Augmented ESBMC processing. Passes the output from ESBMC to an AI model that allows the user to use
natural language to understand the output. As the output from ESBMC can be quite technical in nature.
The AI can also be asked other questions, such as suggestions on how to fix the problem outputted by ESBMC,
and to offer further explanations.

This is an area of research.

[demo.webm](https://user-images.githubusercontent.com/9535618/235352993-b54c47ef-a1c6-422c-aa5b-07edc2988521.webm)

## ESBMC

From the [ESBMC website](http://esbmc.org):

> ESBMC is an open source, permissively licensed, context-bounded model checker
> based on satisfiability modulo theories for the verification of single and
> multi-threaded C/C++ programs. It does not require the user to annotate the
> programs with pre- or postconditions, but allows the user to state additional
> properties using assert-statements, that are then checked as well. Furthermore,
> ESBMC provides two approaches (lazy and schedule recording) to model check
> multi-threaded programs. It converts the verification conditions using different
> background theories and passes them directly to an SMT solver.

From the [ESBMC GitHub repo](https://github.com/esbmc/esbmc)

> The efficient SMT-based context-bounded model checker (ESBMC)

## Initial Setup

1. Install required Python modules: `pip3 install -r requirements.txt`. Alternatively use `pipenv shell` to go into a virtual envrionment and run `pipenv lock`.
2. ESBMC-AI does not come with the original ESBMC software. In order to use ESBMC-AI you must provide ESBMC. Download [ESBMC](http://esbmc.org/) executable or build from [source](https://github.com/esbmc/esbmc).
3. Create a `.env` file using the provided `.env.example` as a template. Make sure to insert your OpenAI API key inside the `.env` file you just created!
4. Enter the ESBMC executable location in the .env `ESBMC_PATH`.
5. Further adjust .env settings as required.
6. You can now run ESBMC-AI.

## Settings

### .env

The following settings are adjustable in the .env file. **Some settings are allowed to be omitted, however, the program will display a warning when done so as it is not a recommended practice**. This list may be incomplete:

1. `OPENAI_API_KEY`: Your OpenAI API key.
2. `ESBMC_AI_CFG_PATH`: ESBMC AI requires a path to a JSON config file, the default path is `./config.json`. This can be changed to another path, if there is a preference for multiple files.

### config.json

The following settings are adjustable in the config.json file. **Some settings are allowed to be omitted, however, the program will display a warning when done so as it is not a recommended practice**. This list may be incomplete:

1. `chat_temperature`: The temperature parameter used when calling the chat completion API. This controls the temperature sampling that the model uses. Higher values like 0.8 and above will make the output more random, on the other hand, lower values like 0.2 will be more deterministic. **Allowed values are between 0.0 to 2.0**. Default is 1.0
2. `ai_model`: The model to use. Options: `gpt-3.5-turbo`, `gpt-4` (under API key conditions).
3. `esbmc_path`: Override the default ESBMC path. Leave blank to use the default ("./esbmc").
4. `cfg_sys_path`: Path to JSON file that contains initial prompt messages for the AI model that give it instructions on how to function.
5. `cfg_initial_prompt_path`: Text file that contains the instructions to initiate the initial prompt, where the AI is asked to walk through the code and explain the ESBMC output.
6. `esbmc_params`: Array of strings. This represents the default ESBMC parameters to use when calling ESBMC, these will be used only when no parameters are specified after the filename. **Do not specify a source file to scan in here as ESBMC-AI will inject that in the ESBMC parameters itself**.
7. `prompts`: Contains the prompts that will be used when setting up/interacting with the AI.
   1. `system`: Array of initial system messages that instruct the AI what its function is. Each element in the array is a struct that contains a `role` field (should ideally be system/assistant) and a `content` field that describes what that role's message content are. This should be a conversation between system and assistant.
   2. `initial`: String that describes the initial prompt given to the AI, after it has read the source code, and the ESBMC output. This field should ask the AI model to explain the source code and ESBMC output.

## Usage

### Basic

ESBMC-AI can be used to scan a file with default parameters like this:

```bash
./main.py /path/to/source_code.c
```

### ESBMC-AI Parameters

Any parameters before the filename will be processed and consumed by ESBMC-AI.
So in this case `-vr` will be consumed by ESBMC-AI, and ESBMC will not get any
arguments.

```bash
./main.py -vr /path/to/source_code.c
```

### Help

```bash
./main.py -h
```

### ESBMC Arguments

Below are some very useful arguments that can be passed to ESBMC:

```
Property checking:
  --no-assertions                  ignore assertions
  --no-bounds-check                do not do array bounds check
  --no-div-by-zero-check           do not do division by zero check
  --no-pointer-check               do not do pointer check
  --no-align-check                 do not check pointer alignment
  --no-pointer-relation-check      do not check pointer relations
  --no-unlimited-scanf-check       do not do overflow check for scanf/fscanf
                                   with unlimited character width.
  --nan-check                      check floating-point for NaN
  --memory-leak-check              enable memory leak check
  --overflow-check                 enable arithmetic over- and underflow check
  --ub-shift-check                 enable undefined behaviour check on shift
                                   operations
  --struct-fields-check            enable over-sized read checks for struct
                                   fields
  --deadlock-check                 enable global and local deadlock check with
                                   mutex
  --data-races-check               enable data races check
  --lock-order-check               enable for lock acquisition ordering check
  --atomicity-check                enable atomicity check at visible
                                   assignments
  --stack-limit bits (=-1)         check if stack limit is respected
  --error-label label              check if label is unreachable
  --force-malloc-success           do not check for malloc/new failure
```

Some examples of passing parameters to ESBMC:

```
./main.py /path/to/source_code.c --force-malloc-success --no-assertions --unwind 5
```

Basically, any arguments **after** the filename are passed directly to ESBMC.

### In-Chat Commands Help

Type the following command when inside the chat:

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
