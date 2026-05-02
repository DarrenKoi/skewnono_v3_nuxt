import vuetify from "eslint-config-vuetify";
import vuePlugin from "eslint-plugin-vue";
import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  ...vuetify(),
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parser: vuePlugin.parser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    files: ["**/*.vue"],
    plugins: {
      vue: vuePlugin,
    },
    rules: {
      // Add Vue 3 specific rules here
      "vue/no-setup-props-destructure": "off", // Allow destructuring props in setup
      "vue/multi-word-component-names": "off", // Not require multi-word component names
      "vue/component-name-in-template-casing": ["error", "PascalCase"],
      "vue/html-self-closing": [
        "error",
        {
          html: {
            void: "always",
            normal: "always",
            component: "always",
          },
        },
      ],
      "vue/script-setup-uses-vars": "error",
      "no-unused-vars": "warn",
    },
  },
];
