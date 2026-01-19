// Firebase disabled by user
/*
const admin = require("firebase-admin");
let serviceAccount;
try {
...
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});
module.exports = admin;
*/
module.exports = {
  auth: () => ({ verifyIdToken: () => Promise.reject("Firebase disabled") }),
  messaging: () => ({ send: () => Promise.resolve("Firebase disabled") })
};
