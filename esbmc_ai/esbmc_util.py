# Author: Yiannis Charalambous

import os
import re
import sys
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
import esbmc_ai.config as config
from esbmc_ai.ai_models import _ai_model_names
from . import config
import nltk
from nltk.tokenize import word_tokenize,sent_tokenize

def optimize_output(output):
    print("Optimiziiiiiingg  aaaaaa")
    return output

def esbmc(path: str, esbmc_params: list):
    """Exit code will be 0 if verification successful, 1 if verification
    failed. And any other number for compilation error/general errors."""
    # Build parameters
    esbmc_cmd = [config.esbmc_path]
    esbmc_cmd.extend(esbmc_params)
    esbmc_cmd.append(path)

    # Run ESBMC and get output
    process = Popen(esbmc_cmd, stdout=PIPE, stderr=STDOUT)
    (output_bytes, err_bytes) = process.communicate()
    # Return
    exit_code = process.wait()
    output: str = str(output_bytes).replace("\\n", "\n")
    err: str = str(err_bytes).replace("\\n", "\n")
    #output = optimize_output(output)  
   # print("HELLO before the call")
    output = esbmc_output_optimisation(output)
   # print("HELLO after the code")
    #sys.stdout.flush()
    return exit_code, output, err

def esbmc_output_optimisation(esbmc_output:str) -> str:
  
    esbmc_output =re.sub(r'^\d+. The output mentions that no solver was specified, so ESBMC defaults to using the Boolector solver\.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'^\d+. This output states that the solving process with the Boolector solver took a certain amount of time\.','', esbmc_output, flags=re.MULTILINE)  
    esbmc_output = re.sub(r'[-]+', '', esbmc_output)  # Remove lines of dashes
    esbmc_output = re.sub(r'\b[0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8}\b', '', esbmc_output)  # Remove hex patterns
    esbmc_output = re.sub(r'^Line \d+: ESBMC is using the Boolector solver \d+\.\d+\.\d+ to solve the encoding\.$', '', esbmc_output, flags=re.MULTILINE)  # Remove Boolector lines
    esbmc_output = re.sub(r'\d+. ESBMC is using the Boolector solver \d+\. \d+\. \d+ to solve the encoding\.$', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'^Line \d+: The solver takes \d+\.\d+s to determine the runtime decision procedure\.$', '', esbmc_output, flags=re.MULTILINE)  # Remove solver time lines
    esbmc_output = re.sub(r'.*Boolector.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output =re.sub(r'/\*.*?\*/', '', esbmc_output, flags=re.MULTILINE)
    pattern = r"- `.*Slicing time: \d+\.\d+s \(removed \d+ assignments\)`.*: ESBMC has performed slicing, a technique that removes irrelevant assignments from the program and reduces the complexity of analysis."
    esbmc_output = re.sub(pattern, '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\n\*s\n', '\n', esbmc_output)
    esbmc_output = esbmc_output.replace("output from ESBMC", "ESBMC output")
    #esbmc_output = re.sub(r'.*runtime decision.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'The time.*', '', esbmc_output, flags=re.MULTILINE) 
    #VCCs represent the assertions in the code that need to be verified
    esbmc_output = re.sub(r'VCCs represent.*', '', esbmc_output, flags=re.MULTILINE)
    #if(config.ai_model.name != "gpt-4-32K"):
    #ESBMC then encodes the remaining VCCs using bitvector and floating-point arithmetic, and displays the time taken for this encoding process.
    esbmc_output = re.sub(r'.*remaining VCCs.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*bitvector.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*floating-point arithmetic.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*encoding.*', '', esbmc_output, flags = re.MULTILINE)
    esbmc_output = re.sub(r'.*GOTO program.*', '', esbmc_output, flags=re.MULTILINE)  
    #Next, ESBMC states that it is starting the runtime decision procedure. This is the step where ESBMC makes concrete assignments to the program variables to check the property being verified.
    #It creates VCCs (verification conditions) and starts encoding them to a solver to solve the constraints.
    #ESBMC encodes these VCCs to a solver, and in this case, the encoding time is shown as 0.019s.
    #ESBMC encodes these VCCs to a solver, and in this case, the encoding time is shown as 0.019s. ESBMC then uses a runtime decision procedure to solve the encoded formulas, which takes 1.351s for this analysis. The decision procedure involves executing various branches of the program symbolically and making decisions based on constraints and conditions.
    esbmc_output = re.sub(r'.*encoding time.*', '', esbmc_output, flags= re.MULTILINE)
    esbmc_output = re.sub(r', which takes \d+\.\d+s \.*', '.', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'The output indicates that ESBMC generates a verification condition \(VCC\) for each possible path and encodes them into a solver\.', '', esbmc_output, flags= re.MULTILINE)
   # esbmc_output = re.sub(r'In this case, the decision procedure took \d+\.\d+s \. seconds.','', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'Measures the [^.]+?encoding time [^.]+?\.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'In this case, the procedure took [0-9.]+ seconds\.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\s*It measures[^.]+? encoding time [^.]+?\.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\.\s*\n', '.\n', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*? GOTO Program[^.]*\.\s*', '', esbmc_output)
    esbmc_output = re.sub(r'.*? GOTO program[^.]*\.\s*', '', esbmc_output)    
    esbmc_output = re.sub(r'\d+\.\d+s \.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*time.*', '', esbmc_output, flags=re.MULTILINE)    
    esbmc_output =  re.sub(r'.*program time: \d+\.\d+s \.', '',esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'"Runtime decision procedure: \d+\. \d+s" \.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\.\s*[^.]*?BMC program time: \d+\.\d+s', '', esbmc_output, flags= re.MULTILINE)
    esbmc_output =re.sub(r'\.\s*[^.]*?Runtime decision procedure: \d+.\d+s', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\d+\.\d+s \.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\.\s*[^.]*?BMC program time: \d+\.\d+s', '', esbmc_output, flags= re.MULTILINE)
    esbmc_output =re.sub(r'\.\s*[^.]*?Runtime decision procedure: \d+.\d+s', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\d+\.\d+s \.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*Symex.*|.*symex.*|.*symbolic execution.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output =re.sub(r'After[^.]*?, the code', 'The program then', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*assignments.*|.*assignment.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*iteratively.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*branches.*', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'.*analysis process.*\s','', esbmc_output, flags=re.MULTILINE )
    esbmc_output = re.sub(r'.*remaining VCC.*\s|.*remaining VCCs.*\s','', esbmc_output)
    esbmc_output = re.sub(r'.*0 VCCs.*', '', esbmc_output, flags= re.MULTILINE) # if there are no more VCCs left, the user is not going to take action in this regard.
    esbmc_output = re.sub(r'Finally, ESBMC confirms that the verfication[^.]"VERIFICATION SUCCESSFUL."', 'Finally, ESBMC indicates a successful verification.', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'Let\'s go through the source code and the output of ESBMC to understand what is happening.|Let\'s go through the code and explain the relevant parts along with the output from ESBMC.', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\.\s*.*"Symex completed in:.*".*\s', '', esbmc_output, flags=re.MULTILINE)

    ##assigments verification

    return esbmc_output

def reduce_output2(esbmc_output: str) -> str:
   
    esbmc_output = re.sub(r'\.\s*[^.]*symbolically execute the program[^.]*\.', '', esbmc_output, flags=re.MULTILINE)

    return esbmc_output

# def remove_runtime_decision_procedure(text):
#     # Tokenize the text into sentences
#     sentences = sent_tokenize(text)
    
#     # Define the pattern to be removed
#     pattern = "Runtime decision procedure:"
#     pattern2 = "BMC program time:"
    
#     # Iterate over each sentence
#     for i in range(len(sentences)):
#         # Tokenize the sentence into words
#         words = word_tokenize(sentences[i])
        
#         # If the pattern is in the sentence, remove it
#         if pattern in words:
#             # Find the index of the pattern
#             index = words.index(pattern)
            
#             # Remove the pattern and the next two words (the time and 's')
#             if len(words) > index + 2 and words[index + 2] == 's':
#                 del words[index:index+3]
            
#             # Join the words back into a sentence
#             sentences[i] = ' '.join(words)
#         if pattern2 in words:
#             index = words.index(pattern2)

#             if len(words) > index+2 and words[index+2] == 's':
#                 del words[index:index+3] 
#             sentences[i] = ' '.join(words)   
    
#     # Join the sentences back into a text
#     modified_text = ' '.join(sentences)
    
#     return modified_text

# text = "This is a test sentence. Runtime decision procedure: 1.387s I want this part to remain."
# print(remove_runtime_decision_procedure(text)) 

def esbmc_load_source_code(
    file_path: str,
    source_code: str,
    esbmc_params: list = config.esbmc_params,
    auto_clean: bool = config.temp_auto_clean,
):
    source_code_path = Path(file_path)

    # Create temp path.
    delete_path: bool = False
    if not os.path.exists(config.temp_file_dir):
        os.mkdir(config.temp_file_dir)
        delete_path = True

    temp_file_path = f"{config.temp_file_dir}{os.sep}{source_code_path.name}"

    # Create temp file.
    with open(temp_file_path, "w") as file:
        # Save to temporary folder and flush contents.
        file.write(source_code)
        file.flush()

        # Call ESBMC to temporary folder.
        results = esbmc(file.name, esbmc_params)

    # Delete temp files and path
    if auto_clean:
        # Remove file
        os.remove(temp_file_path)
        # Remove file path if created this run and is empty.
        if delete_path and len(os.listdir(config.temp_file_dir)) == 0:
            os.rmdir(config.temp_file_dir)

    # Return
    return results
