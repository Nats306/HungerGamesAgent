import Keycloak from "keycloak-js";

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

/** Initialise the session. Returns true if the user is already logged in. */
export function initAuth(): Promise<boolean> {
  return keycloak.init({
    onLoad: "check-sso",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });
}

/** Returns a valid access token, refreshing it if it expires in < 30 s. */
export async function getToken(): Promise<string> {
  try {
    await keycloak.updateToken(30);
  } catch {
    await keycloak.login();
  }
  return keycloak.token!;
}

export const login = () => keycloak.login();
export const register = () => keycloak.register();
export const logout = () => keycloak.logout({ redirectUri: window.location.origin });
