const spec = {
  prompt: `You are comparing a submitted answer to an expert answer on a given question. Here is the data:
    [BEGIN DATA]
    ************
    [Question]: {{{input}}}
    ************
    [Expert]: {{{expected}}}
    ************
    [Submission]: {{{output}}}
    ************
    [END DATA]

    Compare the factual content of the submitted answer with the expert answer. Ignore any differences in style, grammar, or punctuation.
    The submitted answer may either be a subset or superset of the expert answer, or it may conflict with it. Determine which case applies. Answer the question by selecting one of the following options:
    (A) The submitted answer is a subset of the expert answer and is fully consistent with it.
    (B) The submitted answer is a superset of the expert answer and is fully consistent with it.
    (C) The submitted answer contains all the same details as the expert answer.
    (D) There is a disagreement between the submitted answer and the expert answer.
    (E) The answers differ, but these differences don't matter from the perspective of factuality.
    (F) The submitted answer asks for more context, specifics or clarification but provides factual information consistent with the expert answer.
    (G) The submitted answer asks for more context, specifics or clarification but does not provide factual information consistent with the expert answer.`,
  choice_scores: {
    A: 0.4,
    B: 0.6,
    C: 1,
    D: 0,
    E: 1,
    F: 0.2,
    G: 0,
  },
};

export default spec;
