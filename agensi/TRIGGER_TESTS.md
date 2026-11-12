# Trigger tests: Daily US Stock Analysis

Agensi's pre-publish rule: the skill should trigger on 5 of 5 relevant prompts and 0 of 5 unrelated ones. If it
triggers on fewer than 4 relevant prompts, the description is too narrow. If it triggers on more than 1 unrelated
prompt, it is too broad.

Status: **not yet run in an agent.** Run each prompt in a fresh session with the skill installed, tick the box when
the result is right, and record the agent and date. Run again after a model update.

## Should trigger

- [ ] How does AAPL look right now?
- [ ] Rank these for me: MSFT, NVDA, TSLA, BRK.B
- [ ] I have $25,000 and risk 1% a trade. How many shares of AMD can I buy?
- [ ] Is the market risk-on or risk-off today?
- [ ] Where would a stop go on a long in QQQ?

## Should not trigger

- [ ] Explain what an RSI is
- [ ] What did Apple report for earnings last quarter?
- [ ] Write a Python function that computes a moving average
- [ ] What is the price of Bitcoin?
- [ ] Should I buy a house or rent?

## Record

| Agent | Date | Relevant (of 5) | Unrelated that triggered (of 5) |
|---|---|---|---|
