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
        content: "when was the ballon d'or first awarded for female players?",
      },
      {
        role: "assistant",
        content:
          "The Ballon d'Or for female players was first awarded in 2018. The inaugural winner was Ada Hegerberg, a Norwegian striker who plays for Olympique Lyonnais.",
      },
    ],
    input: "who won the men's trophy that year?",
    expected: "In 2018, the men's Ballon d'Or was awarded to Luka Modrić.",
  },
  {
    chat_history: [
      {
        role: "user",
        content: "when did the astros win the world series?",
      },
      {
        role: "assistant",
        content: `The Houston Astros have won the World Series twice:

          2017
          2022

          Their most recent championship was in 2022, when they defeated the Philadelphia Phillies.`,
      },
      {
        role: "user",
        content: "wasn't there a scandal one year when they won?",
      },
      {
        role: "assistant",
        content:
          "Yes, there was a significant scandal associated with the Astros' 2017 World Series win. It was revealed in late 2019 that the team had engaged in an elaborate sign-stealing scheme during the 2017 season, including during their championship run. This scandal involved using technology to illegally steal opposing teams' signs and relay them to Astros batters in real-time. The revelation led to significant controversy, penalties for the team, and ongoing debates about the legitimacy of their 2017 title.",
      },
    ],
    input: "did they get to keep the world series?",
    expected:
      "Yes, the Houston Astros were allowed to keep their 2017 World Series title despite the sign-stealing scandal. Major League Baseball (MLB) did not strip the Astros of their championship, although the team faced other penalties for their actions.",
  },
  {
    chat_history: [
      {
        role: "user",
        content: "Who were the first picks in the NBA and WNBA drafts in 2022?",
      },
      {
        role: "assistant",
        content: `In 2022:

          NBA first pick: Paolo Banchero (Orlando Magic)
          WNBA first pick: Rhyne Howard (Atlanta Dream)`,
      },
      { role: "user", content: "what colleges did they go to?" },
      {
        role: "assistant",
        content: `Paolo Banchero attended Duke University.

          Rhyne Howard played college basketball at the University of Kentucky.`,
      },
    ],
    input: "how many years of college did they play",
    expected: `Paolo Banchero played one year of college basketball at Duke.

      Rhyne Howard played four years of college basketball at Kentucky.`,
  },
  {
    chat_history: [
      { role: "user", content: "what are the grand slams?" },
      {
        role: "assistant",
        content: `The Grand Slams are the four most prestigious annual tennis tournaments:

          1. Australian Open (January)
          2. French Open (May-June)
          3. Wimbledon (June-July)
          4. US Open (August-September)

          These tournaments offer the most ranking points, prize money, and public attention in professional tennis. Winning all four in a single year is called a "Calendar Grand Slam," which is a rare and significant achievement in the sport.`,
      },
      {
        role: "user",
        content: "who was the last player to achieve a calendar grand slam?",
      },
      {
        role: "assistant",
        content: `The last player to achieve a Calendar Grand Slam in singles tennis was Steffi Graf in 1988. She won all four major tournaments (Australian Open, French Open, Wimbledon, and US Open) in the same calendar year. Graf's achievement is even more remarkable because she also won the Olympic gold medal that year, completing what is known as a "Golden Slam."

        No male player has achieved a Calendar Grand Slam in the Open Era (since 1968). The last man to do so was Rod Laver in 1969.`,
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
          "The Carolina Hurricanes won their first and only Stanley Cup in 2006. They defeated the Edmonton Oilers in the finals, winning the series 4-3.",
      },
      {
        role: "user",
        content: "who was the mvp?",
      },
      {
        role: "assistant",
        content:
          "The Conn Smythe Trophy, which is awarded to the most valuable player of the Stanley Cup playoffs, was given to Cam Ward, the goaltender for the Carolina Hurricanes, in 2006.",
      },
    ],
    input: "is he still playing?",
    expected:
      "No, Cam Ward is no longer playing professional hockey. He retired from the NHL in 2019 after playing his final season with the Chicago Blackhawks.",
  },
];

export default dataset;
