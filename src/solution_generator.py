# Author: Yiannis Charalambous 2023


from src.chat import ChatInterface


class SolutionGenerator(ChatInterface):
    initial_prompt: str
    source_code: str
    esbmc_output: str
    attempt: int

    def __init__(
        self,
        system_messages: list,
        initial_prompt: str,
        source_code: str,
        esbmc_output: str,
        model: str,
        temperature: float,
    ) -> None:
        super().__init__(
            system_messages=system_messages,
            model=model,
            temperature=temperature,
        )
        self.initial_prompt = initial_prompt
        self.source_code = source_code
        self.initial_prompt = initial_prompt
        self.esbmc_output = esbmc_output
        self.attempt = 0

        # Introduce source code and ESBMC output to AI.
        self.push_to_message_stack(
            "user",
            f"The following text is the source code of the program, reply OK if you understand:\n\n{source_code}",
        )
        self.push_to_message_stack("assistant", "ok")
        self.push_to_message_stack(
            "user",
            f"The following text is the output of ESBMC, reply OK if you understand:\n\n{esbmc_output}",
        )
        self.push_to_message_stack("assistant", "ok")

    def generate_solution(self) -> str:
        solution: str = (
            self.send_message(self.initial_prompt).choices[0].message.content
        )
        self.attempt += 1
        # Remove previous attempts.
        self.messages.pop(len(self.messages) - 1)
        self.messages.pop(len(self.messages) - 1)
        return solution
