/** Only a stored key can be kept, without one the create hint is the true one. */
export function apiKeyHinweis(isEdit: boolean, keySet: boolean): "dialog.apiKeyEditHint" | "dialog.apiKeyHint" {
  return isEdit && keySet ? "dialog.apiKeyEditHint" : "dialog.apiKeyHint";
}
