# ESBMC AI

AI Augmented ESBMC processing. Passes the output from ESBMC to an AI model that allows the user to use natural language to understand the output. As the output from ESBMC can be quite technical in nature. The AI can also be asked other questions, such as suggestions on how to fix the problem outputted by ESBMC, and to offer further explanations.

This is an area of active research.

![ESBMC-AI Visual Abstract](https://github.com/Yiannis128/esbmc-ai/assets/9535618/1b51c57f-a769-4067-abd9-e81de5e7506b)

## Demonstration

### Basic Usage Demo

[demo.webm](https://user-images.githubusercontent.com/9535618/235352993-b54c47ef-a1c6-422c-aa5b-07edc2988521.webm)

### Fix Code Demo

[demo_fix_code.webm](https://github.com/Yiannis128/esbmc-ai/assets/9535618/e35882ee-7e50-4c10-9879-d19e73d7f45d)

### YouTube Channel

More videos can be found on the [ESBMC-AI Youtube Channel](https://www.youtube.com/@esbmc-ai)

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

## Wiki

For full documentation, see the [ESBMC-AI Wiki](https://github.com/Yiannis128/esbmc-ai/wiki). The README file contains quick setup instructions. For more detailed setup instructions, see the [Initial Setup](https://github.com/Yiannis128/esbmc-ai/wiki/Initial-Setup) page.

## Initial Setup

See [Initial Setup Wiki Page](https://github.com/Yiannis128/esbmc-ai/wiki/Initial-Setup).

## Configuration/Settings

See [Configuration Wiki page](https://github.com/Yiannis128/esbmc-ai/wiki/Configuration).

## Usage

Read about how to run and use ESBMC-AI in [this wiki page](https://github.com/Yiannis128/esbmc-ai/wiki/Initial-Setup#usage).

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

1. Keep the coding style consistent. Use the [Black](https://pypi.org/project/black/) code formatter.
2. Keep the righting style professional.
3. Include comments and function doc-strings.
4. Make sure to update tests as appropriate.

## Acknowledgments

ESBMC-AI is made possible by the following listed entities:

- [ESBMC](https://github.com/esbmc/esbmc)
- [OpenAI Chat API](https://platform.openai.com/docs/guides/chat)
- [Technology Innovation Institute](https://www.tii.ae/)
- [Hugging Face](https://huggingface.co/)
 - [Langchain](https://github.com/langchain-ai/langchain)

## License

[GNU Affero General Public License v3.0](https://github.com/Yiannis128/esbmc-ai/blob/master/LICENSE)
