import { tool } from "ai";
import { z } from "zod";
//Uncomment below to use Braintrust's tracing features
//import { wrapTraced, currentSpan } from "braintrust";

interface LocationInput {
  latitude: number;
  longitude: number;
}

//Create a simple function to note whether or not a Fahrenheit temperature is freezing
//Wrap the function with the wrapTraced function to note inputs and outputs. Uncomment wrapTraced below
const checkFreezing = //wrapTraced(
    async function checkFreezing({ fahrenheit }: {fahrenheit: number}) {
      return fahrenheit < 32;
    }
  //Uncomment below
  // ,{ type: "function" });

//Create a function that takes a temperature in Celsius and returns the temperature in Fahrenheit
//Wrap the function with the wrapTraced function to note inputs and outputs. Uncomment wrapTraced
const convertToFahrenheit = //wrapTraced(
  async function convertToFahrenheit({ celsius }: {celsius: number}) {
    const fahrenheit = (celsius * 9) / 5 + 32;
    const isFreezing = checkFreezing({ fahrenheit });
    return fahrenheit;
  }
//Uncomment below
//,{ type: "tool" });

//Construct a tool using the tool() function in the ai package to place in the LLM call
export const getFahrenheit = tool({
  description: "Convert Celsius to Fahrenheit",
  parameters: z.object({ celsius: z.number() }),
  execute: convertToFahrenheit,
});

//Create a function that fetches a temperature in Celsius from open-meteo
//Wrap the function with the wrapTraced function to note inputs and outputs. Note that the function should be logged as a tool in the trace. Uncomment wrapTraced below
const weatherFunction = //wrapTraced(
  async function weatherFunction({ latitude, longitude }: LocationInput) {
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m&hourly=temperature_2m&daily=sunrise,sunset&timezone=auto`
    );
    const weatherData = await response.json();
    //Uncomment below to add metadata to the span
    // currentSpan().log({
    //   metadata: { foo: "bar" },
    // });
    return weatherData;
  }
  //Uncomment below
  //,{ type: "tool", name: "weatherFunction" });

//Construct a tool using the tool() function in the ai package to place in the LLM call
export const getWeather = tool({
  description: "Get the current weather at a location",
  parameters: z.object({
    latitude: z.number(),
    longitude: z.number(),
  }),
  execute: weatherFunction,
});