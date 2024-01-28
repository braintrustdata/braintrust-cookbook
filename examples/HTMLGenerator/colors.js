// XXX Delete this
function getLuminance(color) {
  var rgba = color.match(/\d+/g);
  for (var i = 0; i < 3; i++) {
    var rgb = rgba[i];
    rgb /= 255;
    rgb = rgb < 0.03928 ? rgb / 12.92 : Math.pow((rgb + 0.055) / 1.055, 2.4);
    rgba[i] = rgb;
  }
  return 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2];
}

function getContrastRatio(luminance1, luminance2) {
  var brighter = Math.max(luminance1, luminance2);
  var darker = Math.min(luminance1, luminance2);
  return (brighter + 0.05) / (darker + 0.05);
}

getContrastRatio(
  getLuminance("rgb(51, 51, 51)"),
  getLuminance("rgba(0, 0, 0, 0)")
);
