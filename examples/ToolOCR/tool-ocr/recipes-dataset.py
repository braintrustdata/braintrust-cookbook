import braintrust

recipes = [
  {"image": "https://images.squarespace-cdn.com/content/v1/5ec6e2030422441e3a7dceeb/1595445920408-QP7Y52ZON1E0J8WEMPQO/un-1.jpg"},
  {"image": "https://static01.nyt.com/images/2012/08/30/business/SMART1/SMART1-jumbo.jpg?quality=75&auto=webp&disable=upscale"},
  
]

main() {
  const dataset = initDataset(PROJECT_NAME, {
    dataset: "Questions",
  });

  for (const question of questions) {
    dataset.insert({
      input: { question: question.question },
      expected: { assertions: question.assertions },
    });
  }

  await dataset.flush();
}

main().catch(console.error);
