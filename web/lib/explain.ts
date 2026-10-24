// Plain-language explanations, shown next to every term the first time it matters.

export const EXPLAIN = {
  chillPortion:
    "Fruit and nut trees need a certain amount of winter cold to wake up and bloom well. Scientists count that cold in chill portions: cool hours add to the count, and warm afternoons can cancel some of it. UC recommends this measure for California.",
  need:
    "How many chill portions this variety needs to bloom well. The numbers come from UC Cooperative Extension research, compiled by Katherine Pope (UC Agriculture and Natural Resources).",
  needSource: "https://ccfruitandnuts.ucanr.edu/node/128184",
  byDate:
    "The date your trees should have collected their chill, roughly when buds start to swell before bloom. The default is a common starting point; change it under Advanced options to match your block. (FNRIC has not yet confirmed these defaults.)",
  odds:
    "We take the chill your orchard has so far, then play the rest of the winter forward using each past winter on record at your spot. '9 in 10' means 9 out of 10 of those winters would get your trees there in time.",
  errorBar:
    "Our estimate of chill so far can be off by about this much. When we tested on real weather stations we had hidden, 8 in 10 tests landed within this range.",
  early:
    "Chill usually starts building in November. Until it does, the forecast is based mostly on past winters at your orchard, and it firms up as the winter goes on.",
  method:
    "We use the nearest weather station with a complete record, adjusted to your exact spot using a 1 km climate map. In our tests on hidden stations this was the most accurate method.",
  replay:
    "Pick a winter you remember and watch how this forecast would have looked week by week, and what actually happened. It shows how much an early-season forecast can change, so you know how much to trust today's.",
  history:
    "Every winter since 1980 at this exact spot, using real station records. Useful when buying land or planting for the next 20 years.",
  heat:
    "After bloom, warmth drives nut and fruit development. Growing degree days add up that warmth from your bloom date.",
  accuracy:
    "How we tested these numbers against real measurements, in plain terms.",
  block:
    "For a whole block we check several spots across it (at least 1 km apart, the size of our climate map's grid) and tell you if chill differs across the block.",
};

// The headline sentence: says what the uncertainty is, not just the color.
export function plainVerdict(level: "green" | "amber" | "red", chanceLow: number, low: number, high: number): string {
  if (level === "green") return "Very likely enough chill in time.";
  if (level === "red") return "Likely not enough chill in time.";
  if (chanceLow >= 0.9 && high > low) return `Very likely to reach the minimum (${low}), but it may fall short of the full ${high}.`;
  return `Could go either way: ${Math.round(chanceLow * 10)} in 10 past winters reached the minimum (${low}) in time.`;
}

export const LEVEL_PLAIN = {
  green: "Very likely enough chill in time.",
  amber: "Probably enough chill, but not certain.",
  red: "Likely not enough chill in time.",
} as const;
