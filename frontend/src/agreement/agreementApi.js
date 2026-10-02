import axios from 'axios';
import { API, authed } from '../sync/api';

export const agreementApi = {
  status: async (getToken) =>
    (await axios.get(`${API}/agreement/status`, await authed(getToken))).data,
  preview: async (getToken, fields) =>
    (await axios.post(`${API}/agreement/preview`, fields, await authed(getToken))).data,
  sign: async (getToken, body) =>
    (await axios.post(`${API}/agreement/sign`, body, await authed(getToken))).data,
  pdfUrl: async (getToken) =>
    (await axios.get(`${API}/agreement/pdf`, await authed(getToken))).data.url,
};

export const FIELD_KEYS = [
  'entity_type', 'legal_name', 'artist_name', 'company_name', 'signer_title',
  'address_line1', 'address_line2', 'city', 'region', 'postal_code', 'country', 'adult_confirmed',
];

export const formatSignedDate = (iso) =>
  new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

// Opens the signed PDF. The URL expires in 5 minutes, so fetch it on click, never ahead of time.
// Use a same-tab navigation, not window.open: Safari blocks popups opened after an await, and the
// presigned URL carries Content-Disposition: attachment, so this downloads the file and the page stays put.
export const openAgreementPdf = async (getToken) => {
  try {
    const url = await agreementApi.pdfUrl(getToken);
    window.location.assign(url);
  } catch (err) {
    console.error('Could not open agreement PDF', err);
  }
};
