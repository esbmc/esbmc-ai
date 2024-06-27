# Author: Yiannis Charalambous

import os
import re
import sys
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
import esbmc_ai.config as config
from . import config
import nltk
from nltk.tokenize import word_tokenize,sent_tokenize
nltk.download('punkt')


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
    output = esbmc_output_optimisation(output)
    output = reduce_output2(output)
    output = remove_patterns_nltk(output)

    return exit_code, output, err

def esbmc_output_optimisation(esbmc_output:str) -> str:
  
    esbmc_output =re.sub(r'(^\d+\.\s*)?The output mentions that no solver was specified, so ESBMC defaults to using the Boolector solver\.', '', esbmc_output)
    esbmc_output = re.sub(r'(^\d+\.\s*)?This output states that the solving process with the Boolector solver took a certain amount of time\.','', esbmc_output)  
    esbmc_output = re.sub(r'[-]+', '', esbmc_output)  # Remove lines of dashes
    
    esbmc_output = re.sub(r'\(*\b[0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8} [0-9a-fA-F]{8}\b\)*', '', esbmc_output)  # Remove hex patterns
    esbmc_output = re.sub(r'^Line \d+: ESBMC is using the Boolector solver \d+\.\d+\.\d+ to solve the encoding\.$', '', esbmc_output)  
    # Remove Boolector lines
    esbmc_output = re.sub(r'\d+. ESBMC is using the Boolector solver \d+\. \d+\. \d+ to solve the encoding\.$', '', esbmc_output)
    
    esbmc_output = re.sub(r'^Line \d+: The solver takes \d+\.\d+s to determine the runtime decision procedure\.$', '', esbmc_output)  
    # Remove solver time lines
    esbmc_output = re.sub(r'.*Boolector.*\n\n', '', esbmc_output)
    pattern = r"- `.*Slicing time: \d+\.\d+s \(removed \d+ assignments\)`.*: ESBMC has performed slicing, a technique that removes irrelevant assignments from the program and reduces the complexity of analysis."
    esbmc_output = re.sub(pattern, '', esbmc_output)
    
    esbmc_output = re.sub(r'\n\s*\n', '\n', esbmc_output)
    esbmc_output = esbmc_output.replace("output from ESBMC", "ESBMC output")
    esbmc_output = re.sub(r'The time.*', '', esbmc_output) 
    
    esbmc_output = re.sub(r'[^.]VCCs represent.*|[^.]These VCCs represent.*', '', esbmc_output) 
    #These types of lines represent some sequences of VCCs that can easily be ommitted for development purposes
    esbmc_output = re.sub(r'.*bitvector.*', '', esbmc_output)
    esbmc_output = re.sub(r'\s*\(\s*`thread\d+`(?:,\s*`thread\d+`)*\s*\)', '', esbmc_output)
    
    esbmc_output = re.sub(r'.*floating-point arithmetic.*', '', esbmc_output)
    esbmc_output = re.sub(r'.*encoding.*', '', esbmc_output)
    esbmc_output = re.sub(r'.*encoding time.*', '', esbmc_output)

    esbmc_output = re.sub(r', which takes \d+\.\d+s\.*', '.', esbmc_output)
    esbmc_output = re.sub(r'The output indicates that ESBMC generates a verification condition \(VCC\) for each possible path and encodes them into a solver\.', '', esbmc_output) #This information can be disregarded for development purposes
    esbmc_output = re.sub(r'Measures the [^.]+?encoding time [^.]+?\.', '', esbmc_output)

    esbmc_output = re.sub(r'In this case, the procedure took [0-9.]+ seconds\.', '', esbmc_output)
    esbmc_output = re.sub(r'\s*It measures[^.]+? encoding time [^.]+?\.', '', esbmc_output)
    esbmc_output = re.sub(r'[^.]*GOTO program[^.]*\.', '', esbmc_output)

    esbmc_output = re.sub(r'\d+\.\d+s \.', '', esbmc_output)
    esbmc_output = re.sub(r'\.\s*.*time.*\n\n|\.\s*[^.]*time[^.]*\.', '', esbmc_output)    
    esbmc_output =  re.sub(r'.*program time: \d+\.\d+s \.', '',esbmc_output)

    esbmc_output = re.sub(r'\.\s*[^.]*?BMC program time:\d+\.\d+s', '', esbmc_output)
    esbmc_output =re.sub(r'\.\s*[^.]*?Runtime decision procedure: \d+.\d+s\"*', '', esbmc_output)
    esbmc_output = re.sub(r'.*Symex.*|.*symex.*|.*symbolic execution.*\n\n', '', esbmc_output)

    esbmc_output =re.sub(r'After[^.]*?, the code', 'The program then', esbmc_output)
    esbmc_output = re.sub(r'.*assignments.*|.*assignment.*', '', esbmc_output)
    esbmc_output = re.sub(r'.*This is done iteratively for all the assigned variables.', '', esbmc_output)

    esbmc_output = re.sub(r'The decision procedure involves executing various branches of the program symbolically and making decisions based on constraints and conditions.', '', esbmc_output)
    #The informations about branches are not necessary relevant to the understanding of bugs
    esbmc_output = re.sub(r'.*analysis process.*\s','', esbmc_output) 
    esbmc_output = re.sub(r'.*remaining VCC.*\s|.*remaining VCCs.*\s','', esbmc_output)

    esbmc_output = re.sub(r'.*0 VCCs.*', '', esbmc_output) # If there are no more VCCs left, the user is not going to take action in this regard.
    esbmc_output = re.sub(r'Finally, ESBMC confirms that the verfication.*"VERIFICATION SUCCESSFUL."', 'Finally, ESBMC indicates a successful verification.', esbmc_output)
    esbmc_output = re.sub(r'Let\'s go through the source code and the output of ESBMC to understand what is happening.|Let\'s go through the code and explain the relevant parts along with the output from ESBMC.', '', esbmc_output)

    esbmc_output = re.sub(r'\.\s*.*"Symex completed in:.*".*\s', '', esbmc_output)
    esbmc_output = re.sub(r'.*These warnings are about.*', '', esbmc_output) #Warning information are not useful for debugging purposes
   
    esbmc_output = re.sub(r'Let\'s go through the source code and the output of ESBMC to understand what is happening.|Let\'s go through the code and explain the relevant parts along with the output from ESBMC.', '', esbmc_output)
    esbmc_output = re.sub(r'Let\'s[^.]the[^.]code and explain the relevant parts of the output from ESBMC.', '', esbmc_output)
    esbmc_output = re.sub(r'virtual_table::std::.*', '', esbmc_output)

    esbmc_output = re.sub(r'foo =.*', '', esbmc_output)
    esbmc_output = re.sub(r'the .*Efficient SMT-Based Context-Bounded Model Checker \(ESBMC\)', 'ESBMC', esbmc_output)
    esbmc_output = re.sub(r'(Efficient SMT-Based Bounded Model Checker)', '', esbmc_output)      
    

    return esbmc_output


def reduce_output2(esbmc_output: str) -> str:
    
    pattern1 = re.compile(r'\.\s*[^.]*symbolically execute the program[^.]*\.')
    esbmc_output = pattern1.sub('', esbmc_output)  #Reffers to a time measurement
   
    esbmc_output = esbmc_output.replace('In this case, it initially starts with', 'It starts with') 
    esbmc_output = re.sub(r'(.*)\s*before moving forward', r'\1', esbmc_output) #removes the specified sequence, as it is trivial

    pattern3 = re.compile('.*k=0.*') # for k=0, which is the base case, there is no need for an explanation for development purposes, the user would not find this information helpful 
    esbmc_output = pattern3.sub('', esbmc_output) 
    esbmc_output = re.sub('the Efficient SMT-Based Context-Bounded Model Checker \(ESBMC\)', 'ESBMC', esbmc_output)
    
    esbmc_output = esbmc_output.replace(', which stands for Efficient SMT-Based Context-Bounded Model Checker', '.')   
    pattern4 = re.compile('.*Warnings.*|.*warnings.*')
    esbmc_output = pattern4.sub('', esbmc_output)

    pattern5 = re.compile('.*\*Warnings\*\*.*')
    esbmc_output = pattern5.sub('', esbmc_output)
    
    pattern6 = re.compile('.*warning.*')
    esbmc_output = pattern6.sub('', esbmc_output)     
       
    pattern7 = re.compile('.*A series of warnings.*')
    esbmc_output =  pattern7.sub('', esbmc_output)
    
    esbmc_output = re.sub('ESBMC \(the Efficient SMT-based Context-Bounded Model Checker\)', 'ESBMC', esbmc_output) 
    pattern8 = re.compile('These messages relate how ESBMC handles loops.*\.|These messages relate.*\.') #These type of lines can be ommitted, if there is anything relevant about loops, ESBMC-AI can display other more precise explanations
    esbmc_output = pattern8.sub('', esbmc_output) 

    esbmc_output= esbmc_output.replace('which, in simple terms', 'which')
    esbmc_output = re.sub(r'After[^.]*iterations[^.]*\.', '', esbmc_output) #These types of line can be removed to make the output easier to read, without ommitting any important information   


    esbmc_output = esbmc_output.replace('Initially, ESBMC parses the given source file. It identifies', 'ESBMC identifies')
    pattern11 = re.compile('\.\s*.parsing the source file.*|\.\s*.parses the source file.*|\s*.*parsing the source file.*|\s*.*starts by parsing the program.*|\s*.*starts by parsing the.*') # this is an additional information that ESBMC-AI provides, it is not useful for understanding the behaviour of the tested code
    
    esbmc_output = pattern11.sub('', esbmc_output)
    pattern12 = re.compile('\*\*Parsing and Compilation Warnings:\*\*') #This represents a type of header in the output, which is followed by an explanatory paragraph, its removal doesn't affect the understandability of the parsing and warning explanations
    esbmc_output = pattern12.sub('', esbmc_output)

    esbmc_output = re.sub(r'### Conclusion.*(?:\n{2,}|$)|### In Conclusion.*(?:\n{2,}|$)', '', esbmc_output, flags=re.MULTILINE)
    esbmc_output = re.sub(r'\*\*Conclusion:\*\*.*(?:\n{2,}|$)', '', esbmc_output, flags=re.MULTILINE)  

    esbmc_output = esbmc_output.replace(", revealing the tool's version for this context", '.')    
    esbmc_output = re.sub(r'exit condition \(`break`, `return`,.*?\)', 'exit condition (like `break` or `return`)', esbmc_output) #keeps the message concise, displays only the relevant information 
    

    esbmc_output = re.sub(r'.*Slicing.*\.|.*slicing.*\.', '', esbmc_output) #Slicing information doesn't help for understanding bugs or approach them differently
    pattern16 = re.compile('The output contains.*are not relevant.*\n')
   
    esbmc_output = pattern16.sub('', esbmc_output)
    esbmc_output = re.sub(r'.*(`ESBMC-boolector`).*', '', esbmc_output) 

    esbmc_output = esbmc_output.replace('such as the decision procedure used (`ESBMC-boolector`) and', 'such as')
    pattern16 = re.compile('These details are not directly related to understanding the vulnerabilities in the code.*|\.\s*.*are not direclty related to understanding the vulnerabilities.*|\.\s*.*are not relevant to understanding the vulnerabilities.*')
    
    esbmc_output = pattern16.sub('', esbmc_output)
    pattern17 = re.compile('\s*\(\s*`thread\d+`(?:,\s*`thread\d+`)*\s*\)') #It is not neccesary to mention threads in parantheses, as they are all explained afterwards
    esbmc_output = pattern17.sub('', esbmc_output)

    esbmc_output = re.sub(r'^\s*\n', '', esbmc_output)
    pattern19 = re.compile('^\s*\n')
    esbmc_output = pattern19.sub('', esbmc_output)
    
    esbmc_output = re.sub(r'\n{2,}', '\n', esbmc_output)
    pattern20 = re.compile(': The version of ESBMC.*')
    esbmc_output = pattern20.sub('', esbmc_output) 

    esbmc_output = re.sub(r'\*\*"No bug has been found in the base case"\*\*:.*', '**"No bug has been found in the base case"**', esbmc_output)
    esbmc_output = esbmc_output.replace(r' This suggests that the system modeled by the program, under the constraints and assertions defined, behaves as expected without leading to any undesired or erroneous states within the bounded context.', '') #The output is more concise without this sentence, and all relevant aspects are still provided.
    
    return esbmc_output

def remove_patterns_nltk(text):
    # Tokenize the text into sentences
    sentences = text.split('\n')
    # Define the pattern to be removed
    pattern = "Runtime decision procedure:"
    pattern2 = "BMC program time:"
    thread_pattern = re.compile(r'\(`thread\d+`(?:,\s*`thread\d+`)*\)\s', re.IGNORECASE)
    warning_pattern = re.compile(r'- \*\*Warnings\*\*:.*', re.IGNORECASE)
    warning_pattern2 = re.compile(r'A series of wanings are issued', re.IGNORECASE)    
    conclusion_pattern = re.compile(r'### In Conclusion ###.*', re.IGNORECASE)
    bmc_time = re.compile(r'BMC program time:\d+\.\d+s')    
    runtime_pattern =re.compile(r'Runtime decision procedure:\d+\.\d+s')
    boolector_solver = re.compile(r'.*Boolector solver.*')
    # Iterate over each sentence
    for i in range(len(sentences)):
        # Tokenize the sentence into words
        words = word_tokenize(sentences[i])
        # If the pattern is in the sentence, remove it
        if pattern in words:
            # Find the index of the pattern
            index = words.index(pattern)
            # Remove the pattern and the next two words (the time and 's')
            if len(words) > index + 2 and words[index + 2] == 's':
                del words[index:index+3]
            # Join the words back into a sentence
            sentences[i] = ' '.join(words)
        if pattern2 in words:
            index = words.index(pattern2)
            if len(words) > index+2 and words[index+2] == 's':
                del words[index:index+3] 
            sentences[i] = ' '.join(words)   
    # Remove thread patterns
    cleaned_sentences = [thread_pattern.sub('', sentence) for sentence in sentences]
    cleaned_sentences = [warning_pattern.sub('', sentence) for sentence in cleaned_sentences]
    cleaned_sentences = [warning_pattern2.sub('', sentence) for sentence in cleaned_sentences]
    cleaned_sentences = [conclusion_pattern.sub('', sentence) for sentence in cleaned_sentences]
    cleaned_sentences = [bmc_time.sub('', sentence) for sentence in cleaned_sentences]
    cleaned_sentences = [runtime_pattern.sub('', sentence) for sentence in cleaned_sentences]
    cleaned_sentences = [boolector_solver.sub('', sentence) for sentence in cleaned_sentences]        
    cleaned_sentences = [line for line in cleaned_sentences if line.strip() !='']

    # Join the sentences back into a text
    modified_text = '\n'.join(cleaned_sentences)
    
    return modified_text


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
