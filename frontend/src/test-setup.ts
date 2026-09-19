import { GlobalRegistrator } from "@happy-dom/global-registrator";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

GlobalRegistrator.register();

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
