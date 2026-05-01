import nextConfig from "eslint-config-next";

export default [
  ...nextConfig({
    rootDir: ".",
  }),
  {
    rules: {
      "react/no-unescaped-entities": "off",
    },
  },
];
