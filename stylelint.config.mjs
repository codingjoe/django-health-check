import { createRequire } from 'node:module';

// Stylelint 17 ignores NODE_PATH, where pre-commit installs additional_dependencies.
const require = createRequire(import.meta.url);

export default {
  extends: [require.resolve('stylelint-config-standard')],
};
