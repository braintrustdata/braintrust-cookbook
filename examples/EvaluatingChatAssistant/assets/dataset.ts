type DataPoint = {
  chat_history: {
    role: "user" | "assistant";
    content: string;
  }[];
  input: string;
  expected: string;
};

const dataset: DataPoint[] = [
  {
    chat_history: [
      {
        role: "user",
        content: "when did the astros win the world series?",
      },
      {
        role: "assistant",
        content:
          "The Houston Astros have won the World Series twice. Their first victory was in 2017, and their second was in 2022.",
      },
      {
        role: "user",
        content: "wasn't there a scandal one year when they won?",
      },
      {
        role: "assistant",
        content: `Yes, there was a scandal involving the Houston Astros' 2017 World Series win. In late 2019, it was revealed that the Astros had used a sign-stealing scheme during the 2017 season and part of the 2018 season. The team used a camera system to illegally steal opposing teams' signs and relay the information to their hitters.

            The investigation led to significant penalties from Major League Baseball (MLB), including suspensions for the team's manager, A.J. Hinch, and general manager, Jeff Luhnow, both of whom were subsequently fired by the Astros. The team was also fined $5 million and forfeited their first- and second-round draft picks for the 2020 and 2021 drafts.`,
      },
    ],
    input: "did they get to keep the world series?",
    expected:
      "Yes, the Houston Astros were allowed to keep their 2017 World Series title despite the scandal. MLB Commissioner Rob Manfred decided not to strip the team of their championship, stating that there was no precedent for taking away a World Series title and that it would be difficult to determine the extent to which the sign-stealing directly affected the outcome. This decision has been a subject of controversy and debate among fans and players.",
  },
  {
    chat_history: [
      {
        role: "user",
        content: "Who were the first picks in the NBA and WNBA drafts in 2022?",
      },
      {
        role: "assistant",
        content:
          "In 2022, the first picks in the NBA and WNBA drafts were: - **NBA Draft 2022**: Paolo Banchero was selected as the first overall pick by the Orlando Magic. - **WNBA Draft 2022**: Rhyne Howard was selected as the first overall pick by the Atlanta Dream.",
      },
      { role: "user", content: "what colleges did they go to?" },
      {
        role: "assistant",
        content:
          "- **Paolo Banchero** attended Duke University. - **Rhyne Howard** attended the University of Kentucky.",
      },
    ],
    input: "how many years of college did they play",
    expected:
      "- **Paolo Banchero** played one year of college basketball at Duke University before entering the NBA Draft. - **Rhyne Howard** played four years of college basketball at the University of Kentucky before entering the WNBA Draft.",
  },
  {
    chat_history: [
      {
        role: "user",
        content: "when was the ballon d'or first awarded for female players?",
      },
      {
        role: "assistant",
        content:
          "The Ballon d'Or Féminin, awarded to the best female football player in the world, was first introduced in 2018. The inaugural winner was Ada Hegerberg of Norway, who played for Olympique Lyonnais at the time.",
      },
    ],
    input: "who won the men's trophy that year?",
    expected:
      "The men's Ballon d'Or trophy in 2018 was won by Luka Modrić of Croatia, who played for Real Madrid.",
  },
  {
    chat_history: [
      { role: "user", content: "what are the grand slams?" },
      {
        role: "assistant",
        content: `The term "Grand Slam" in tennis refers to the four most prestigious tournaments in the sport. These tournaments are held annually and include:

            1. **Australian Open**:
              - **Location**: Melbourne, Australia
              - **Surface**: Hard court
              - **Time of Year**: January

            2. **French Open (Roland Garros)**:
              - **Location**: Paris, France
              - **Surface**: Clay
              - **Time of Year**: Late May to early June

            3. **Wimbledon**:
              - **Location**: London, England
              - **Surface**: Grass
              - **Time of Year**: Late June to early July

            4. **US Open**:
              - **Location**: New York City, USA
              - **Surface**: Hard court
              - **Time of Year**: Late August to early September

            Winning all four tournaments in a single calendar year is known as a "Calendar Year Grand Slam," a rare and significant achievement in tennis.`,
      },
      {
        role: "user",
        content:
          "who was the last player to achieve a grand slam in a single year>",
      },
      {
        role: "assistant",
        content: `The last player to win a Calendar Year Grand Slam in singles tennis was Steffi Graf in 1988. She won all four major tournaments (Australian Open, French Open, Wimbledon, and US Open) in a single calendar year. In addition, she also won the gold medal in women's singles at the 1988 Seoul Olympics, completing what is known as the "Golden Slam."`,
      },
    ],
    input: "where is she from?",
    expected: "Steffi Graf is from Germany.",
  },
  {
    chat_history: [
      {
        role: "user",
        content: "when did the hurricanes win the stanely cup?",
      },
      {
        role: "assistant",
        content:
          "The Carolina Hurricanes won the Stanley Cup in 2006. They defeated the Edmonton Oilers in a seven-game series to capture their first championship.",
      },
      {
        role: "user",
        content: "who was the mvp?",
      },
      {
        role: "assistant",
        content:
          "The MVP of the 2006 Stanley Cup Finals was Cam Ward, the goaltender for the Carolina Hurricanes. He was awarded the Conn Smythe Trophy for his outstanding performance throughout the playoffs.",
      },
    ],
    input: "is he still playing?",
    expected:
      "No, Cam Ward is no longer playing professional hockey. He announced his retirement from the NHL on August 28, 2019. Ward signed a one-day contract with the Carolina Hurricanes to retire as a member of the team where he spent the majority of his career.",
  },
];

export default dataset;
