import pandas as pd
from nltk import edit_distance
from bleu import corpus_bleu, SmoothingFunction
import weighted_ngram_match
import syntax_match
import dataflow_match

from rouge_score import rouge_scorer

def spacify(line):
    testString = []
    specialsPair = [ ['=', '='], ['+', '+'], ['-', '-'], ['+', '='], ['-', '='], ['*', '='], 
                            ['/', '='], ['%', '='], ['!', '='], ['>', '='], ['<', '='], ['&', '&'], 
                            ['|', '|'], ['<', '<'], ['>', '>'], ['-', '>'] ]
    specials = ['(', ')', '{', '}', '[', ']', ',', '.', ';', '+', '-', '*', '/', '%', '=', '>', '<', '!', '&', '^', '\"', '\'']

    inQuotes = False
    for i in range(0, len(line)):
        isSpecial = False
        
        # Check start of string literal
        if not inQuotes and line[i] == '"': 
            inQuotes = True
        # Check end of string literal
        elif inQuotes and line[i] == '"':
            inQuotes = False

        if not inQuotes:
            # Checking for special character modifications (e.g. inclusion of spaces) if not in a string literal
            for c in range(0, len(specialsPair)):
                # Matching compound operators (e.g. ++, -- etc.)
                if i < len(line) -1:
                    if line[i] == specialsPair[c][0] and line[i+1] == specialsPair[c][1]:
                        isSpecial = True
                        if len(testString) > 0:
                            if testString[len(testString)-1] != ' ':
                                testString.append(' ')
                        else:
                            testString.append(' ')

                        testString.append(specialsPair[c][0])
                        testString.append(specialsPair[c][1])
                        if i+1 < len(line) and line[i+1] != ' ':
                            testString.append(' ')
                        i += 1
                    
            if not isSpecial:
                # If no special compound operator is found, check for single special operators
                for c in range(0, len(specials)):
                    if line[i] == specials[c]:
                        if (line[i] == '.' and i > 0 and i < len(line)-1 and line[i+1].isdigit()):
                            # Avoiding spacifying dots in floats
                            continue

                        isSpecial = True
                        if i > 0 and line[i-1] != ' ':
                            if len(testString) > 0:
                                if testString[len(testString)-1] != ' ':
                                    testString.append(' ')
                            else:
                                testString.append(' ')
                            
                        testString.append(specials[c])
                        if i+1 < len(line) and line[i+1] != ' ':
                            testString.append(' ')
                    
        if not isSpecial and line[i] == '\n':
            # Skipping newlines because the ATLAS dataset format has no newlines in a sample
            testString.append(' ')
        elif not isSpecial and line[i] == '\r':
            if len(testString) > 0 and testString[len(testString)-1] != ' ':
                testString.append(' ')
        elif not isSpecial:
            # Non-special character should be included in the dataset without any modifications
            testString.append(line[i])
        
    testStringOut = ''.join([val for val in testString])

    return testStringOut

def prepare_refs_hyps(data):
    references = []
    hypotheses = []

    def group(df_slice):
        refs = []
        for idx, row in df_slice.iterrows():
            refs.append(spacify(row['GenOracle'].replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '')))
        references.append(refs)
        hypotheses.append(spacify(df_slice.iloc[0]['TrueOracle'].replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '')))
        
    data.groupby(['TestID']).apply(group)

    return references, hypotheses

def bleu(data):
    references, hypotheses = prepare_refs_hyps(data)

    return corpus_bleu(references, hypotheses, weights=[0.25, 0.25, 0.25, 0.25], smoothing_function=SmoothingFunction().method2)

def code_bleu(data):
    references, hypotheses = prepare_refs_hyps(data)

    alpha,beta,gamma,theta=0.25,0.25,0.25,0.25

    # calculate ngram match (BLEU)
    tokenized_hyps = [x.split() for x in hypotheses]
    tokenized_refs = [[x.split() for x in reference] for reference in references]

    ngram_match_score = corpus_bleu(tokenized_refs,tokenized_hyps)

    # calculate weighted ngram match
    lang = 'java'
    keywords = [x.strip() for x in open('keywords/'+lang+'.txt', 'r', encoding='utf-8').readlines()]
    def make_weights(reference_tokens, key_word_list):
        return {token:1 if token in key_word_list else 0.2 \
                for token in reference_tokens}
    tokenized_refs_with_weights = [[[reference_tokens, make_weights(reference_tokens, keywords)]\
                for reference_tokens in reference] for reference in tokenized_refs]

    weighted_ngram_match_score = weighted_ngram_match.corpus_bleu(tokenized_refs_with_weights,tokenized_hyps)

    # calculate syntax match
    syntax_match_score = syntax_match.corpus_syntax_match(references, hypotheses, lang)

    # calculate dataflow match
    dataflow_match_score = dataflow_match.corpus_dataflow_match(references, hypotheses, lang)

    # print('ngram match: {0}, weighted ngram match: {1}, syntax_match: {2}, dataflow_match: {3}'.\
    #                    format(ngram_match_score, weighted_ngram_match_score, syntax_match_score, dataflow_match_score))

    code_bleu_score = alpha*ngram_match_score\
                    + beta*weighted_ngram_match_score\
                    + gamma*syntax_match_score\
                    + theta*dataflow_match_score

    # print('CodeBLEU score: ', code_bleu_score)

    return code_bleu_score

def rouge(data):
    score = 0
    scorer = rouge_scorer.RougeScorer(['rougeL'])

    for true, pred in zip(data['TrueOracle'], data['GenOracle']):
        true = spacify(true.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', ''))
        pred = spacify(pred.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', ''))
        
        score = scorer.score(true, pred)['rougeL'][2] # 2 for fmeasure

    return score/len(data)

def edit_sim(data):
    score = 0
    for true, pred in zip(data['TrueOracle'], data['GenOracle']):
        true = true.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '').replace(' ', '')
        pred = pred.replace('org.junit.Assert.', '').replace('org.junit.', '').replace('Assert.', '').replace(' ', '')

        score += edit_distance(true, pred)/max(len(true), len(pred))

    return 1-score/len(data)

def main():
    dataOGPT = pd.read_csv('../../prelim_res.csv', sep='\t', usecols=['TestID', 'TrueOracle', 'GenOracle'])
    dataTeco = pd.read_csv('../../teco_eval/teco/output/preds_processed.csv', sep='\t', usecols=['TestID', 'TrueOracle', 'GenOracle'])

    print('OGPT BLEU: {}'.format(bleu(dataOGPT)))
    print('Teco BLEU: {}'.format(bleu(dataTeco)))

    # print('OGPT CodeBLEU: {}'.format(code_bleu(dataOGPT)))
    # print('Teco CodeBLEU: {}'.format(code_bleu(dataTeco)))

    print('OGPT Rouge: {}'.format(rouge(dataOGPT)))
    print('Teco Rouge: {}'.format(rouge(dataTeco)))

    print('OGPT Edit Distance: {}'.format(edit_sim(dataOGPT)))
    print('Teco Edit Distance: {}'.format(edit_sim(dataTeco)))

main()
