"use client";

import { useTheme } from "next-themes";
import { MouseEvent, useEffect, useMemo, useState, useCallback } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { geoEqualEarth, geoGraticule, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";

const TARGET = {
    name: "CloudSentinel HQ",
    lat: 4.5,
    lng: 101.6869,
};

interface ThreatMapProps {
    onRegionClick?: (region: string | null) => void;
    selectedRegion?: string | null;
    underAttack?: boolean;
    threatLogs?: ThreatLog[];
}

type TooltipDetails = {
    label: string;
    value: string;
};

type TooltipState = {
    title: string;
    subtitle?: string;
    details?: TooltipDetails[];
    x: number;
    y: number;
};

const WIDTH = 800;
const HEIGHT = 400;
const COUNTRY_COORDS: Record<string, { name: string; lat: number; lng: number; color: string }> = {
    AD: { name: "Andorra", lat: 42.5, lng: 1.6, color: "#f43f5e" },
    AE: { name: "United Arab Emirates", lat: 24, lng: 54, color: "#ec4899" },
    AF: { name: "Afghanistan", lat: 33, lng: 65, color: "#3b82f6" },
    AG: { name: "Antigua and Barbuda", lat: 17.05, lng: -61.8, color: "#ec4899" },
    AI: { name: "Anguilla", lat: 18.25, lng: -63.1667, color: "#14b8a6" },
    AL: { name: "Albania", lat: 41, lng: 20, color: "#8b5cf6" },
    AM: { name: "Armenia", lat: 40, lng: 45, color: "#f43f5e" },
    AN: { name: "Netherlands Antilles", lat: 12.25, lng: -68.75, color: "#10b981" },
    AO: { name: "Angola", lat: -12.5, lng: 18.5, color: "#06b6d4" },
    AQ: { name: "Antarctica", lat: -90, lng: 0, color: "#3b82f6" },
    AR: { name: "Argentina", lat: -34, lng: -64, color: "#ec4899" },
    AS: { name: "American Samoa", lat: -14.3333, lng: -170, color: "#14b8a6" },
    AT: { name: "Austria", lat: 47.3333, lng: 13.3333, color: "#ec4899" },
    AU: { name: "Australia", lat: -27, lng: 133, color: "#06b6d4" },
    AW: { name: "Aruba", lat: 12.5, lng: -69.9667, color: "#8b5cf6" },
    AZ: { name: "Azerbaijan", lat: 40.5, lng: 47.5, color: "#f59e0b" },
    BA: { name: "Bosnia and Herzegovina", lat: 44, lng: 18, color: "#10b981" },
    BB: { name: "Barbados", lat: 13.1667, lng: -59.5333, color: "#14b8a6" },
    BD: { name: "Bangladesh", lat: 24, lng: 90, color: "#10b981" },
    BE: { name: "Belgium", lat: 50.8333, lng: 4, color: "#06b6d4" },
    BF: { name: "Burkina Faso", lat: 13, lng: -2, color: "#8b5cf6" },
    BG: { name: "Bulgaria", lat: 43, lng: 25, color: "#f43f5e" },
    BH: { name: "Bahrain", lat: 26, lng: 50.55, color: "#f43f5e" },
    BI: { name: "Burundi", lat: -3.5, lng: 30, color: "#10b981" },
    BJ: { name: "Benin", lat: 9.5, lng: 2.25, color: "#3b82f6" },
    BM: { name: "Bermuda", lat: 32.3333, lng: -64.75, color: "#ec4899" },
    BN: { name: "Brunei Darussalam", lat: 4.5, lng: 114.6667, color: "#14b8a6" },
    BO: { name: "Bolivia, Plurinational State of", lat: -17, lng: -65, color: "#f59e0b" },
    BR: { name: "Brazil", lat: -10, lng: -55, color: "#10b981" },
    BS: { name: "Bahamas", lat: 24.25, lng: -76, color: "#14b8a6" },
    BT: { name: "Bhutan", lat: 27.5, lng: 90.5, color: "#3b82f6" },
    BV: { name: "Bouvet Island", lat: -54.4333, lng: 3.4, color: "#f43f5e" },
    BW: { name: "Botswana", lat: -22, lng: 24, color: "#8b5cf6" },
    BY: { name: "Belarus", lat: 53, lng: 28, color: "#10b981" },
    BZ: { name: "Belize", lat: 17.25, lng: -88.75, color: "#f59e0b" },
    CA: { name: "Canada", lat: 60, lng: -95, color: "#3b82f6" },
    CC: { name: "Cocos (Keeling) Islands", lat: -12.5, lng: 96.8333, color: "#14b8a6" },
    CD: { name: "Congo, the Democratic Republic of the", lat: 0, lng: 25, color: "#8b5cf6" },
    CF: { name: "Central African Republic", lat: 7, lng: 21, color: "#14b8a6" },
    CG: { name: "Congo", lat: -1, lng: 15, color: "#8b5cf6" },
    CH: { name: "Switzerland", lat: 47, lng: 8, color: "#06b6d4" },
    CI: { name: "Côte d'Ivoire", lat: 8, lng: -5, color: "#10b981" },
    CK: { name: "Cook Islands", lat: -21.2333, lng: -159.7667, color: "#06b6d4" },
    CL: { name: "Chile", lat: -30, lng: -71, color: "#06b6d4" },
    CM: { name: "Cameroon", lat: 6, lng: 12, color: "#f59e0b" },
    CN: { name: "China", lat: 35, lng: 105, color: "#f59e0b" },
    CO: { name: "Colombia", lat: 4, lng: -72, color: "#14b8a6" },
    CR: { name: "Costa Rica", lat: 10, lng: -84, color: "#f59e0b" },
    CU: { name: "Cuba", lat: 21.5, lng: -80, color: "#10b981" },
    CV: { name: "Cape Verde", lat: 16, lng: -24, color: "#10b981" },
    CX: { name: "Christmas Island", lat: -10.5, lng: 105.6667, color: "#8b5cf6" },
    CY: { name: "Cyprus", lat: 35, lng: 33, color: "#f43f5e" },
    CZ: { name: "Czech Republic", lat: 49.75, lng: 15.5, color: "#8b5cf6" },
    DE: { name: "Germany", lat: 51, lng: 9, color: "#3b82f6" },
    DJ: { name: "Djibouti", lat: 11.5, lng: 43, color: "#f43f5e" },
    DK: { name: "Denmark", lat: 56, lng: 10, color: "#14b8a6" },
    DM: { name: "Dominica", lat: 15.4167, lng: -61.3333, color: "#06b6d4" },
    DO: { name: "Dominican Republic", lat: 19, lng: -70.6667, color: "#ec4899" },
    DZ: { name: "Algeria", lat: 28, lng: 3, color: "#8b5cf6" },
    EC: { name: "Ecuador", lat: -2, lng: -77.5, color: "#06b6d4" },
    EE: { name: "Estonia", lat: 59, lng: 26, color: "#ec4899" },
    EG: { name: "Egypt", lat: 27, lng: 30, color: "#8b5cf6" },
    EH: { name: "Western Sahara", lat: 24.5, lng: -13, color: "#14b8a6" },
    ER: { name: "Eritrea", lat: 15, lng: 39, color: "#ec4899" },
    ES: { name: "Spain", lat: 40, lng: -4, color: "#06b6d4" },
    ET: { name: "Ethiopia", lat: 8, lng: 38, color: "#10b981" },
    FI: { name: "Finland", lat: 64, lng: 26, color: "#10b981" },
    FJ: { name: "Fiji", lat: -18, lng: 175, color: "#10b981" },
    FK: { name: "Falkland Islands (Malvinas)", lat: -51.75, lng: -59, color: "#3b82f6" },
    FM: { name: "Micronesia, Federated States of", lat: 6.9167, lng: 158.25, color: "#8b5cf6" },
    FO: { name: "Faroe Islands", lat: 62, lng: -7, color: "#3b82f6" },
    FR: { name: "France", lat: 46, lng: 2, color: "#8b5cf6" },
    GA: { name: "Gabon", lat: -1, lng: 11.75, color: "#f43f5e" },
    GB: { name: "United Kingdom", lat: 54, lng: -2, color: "#06b6d4" },
    GD: { name: "Grenada", lat: 12.1167, lng: -61.6667, color: "#3b82f6" },
    GE: { name: "Georgia", lat: 42, lng: 43.5, color: "#f43f5e" },
    GF: { name: "French Guiana", lat: 4, lng: -53, color: "#3b82f6" },
    GG: { name: "Guernsey", lat: 49.5, lng: -2.56, color: "#14b8a6" },
    GH: { name: "Ghana", lat: 8, lng: -2, color: "#ec4899" },
    GI: { name: "Gibraltar", lat: 36.1833, lng: -5.3667, color: "#14b8a6" },
    GL: { name: "Greenland", lat: 72, lng: -40, color: "#14b8a6" },
    GM: { name: "Gambia", lat: 13.4667, lng: -16.5667, color: "#06b6d4" },
    GN: { name: "Guinea", lat: 11, lng: -10, color: "#8b5cf6" },
    GP: { name: "Guadeloupe", lat: 16.25, lng: -61.5833, color: "#14b8a6" },
    GQ: { name: "Equatorial Guinea", lat: 2, lng: 10, color: "#ec4899" },
    GR: { name: "Greece", lat: 39, lng: 22, color: "#14b8a6" },
    GS: { name: "South Georgia and the South Sandwich Islands", lat: -54.5, lng: -37, color: "#f43f5e" },
    GT: { name: "Guatemala", lat: 15.5, lng: -90.25, color: "#8b5cf6" },
    GU: { name: "Guam", lat: 13.4667, lng: 144.7833, color: "#14b8a6" },
    GW: { name: "Guinea-Bissau", lat: 12, lng: -15, color: "#ec4899" },
    GY: { name: "Guyana", lat: 5, lng: -59, color: "#3b82f6" },
    HK: { name: "Hong Kong", lat: 22.25, lng: 114.1667, color: "#f59e0b" },
    HM: { name: "Heard Island and McDonald Islands", lat: -53.1, lng: 72.5167, color: "#06b6d4" },
    HN: { name: "Honduras", lat: 15, lng: -86.5, color: "#f59e0b" },
    HR: { name: "Croatia", lat: 45.1667, lng: 15.5, color: "#8b5cf6" },
    HT: { name: "Haiti", lat: 19, lng: -72.4167, color: "#ec4899" },
    HU: { name: "Hungary", lat: 47, lng: 20, color: "#10b981" },
    ID: { name: "Indonesia", lat: -5, lng: 120, color: "#14b8a6" },
    IE: { name: "Ireland", lat: 53, lng: -8, color: "#14b8a6" },
    IM: { name: "Isle of Man", lat: 54.23, lng: -4.55, color: "#3b82f6" },
    IN: { name: "India", lat: 20, lng: 77, color: "#f59e0b" },
    IO: { name: "British Indian Ocean Territory", lat: -6, lng: 71.5, color: "#06b6d4" },
    IQ: { name: "Iraq", lat: 33, lng: 44, color: "#ec4899" },
    IR: { name: "Iran, Islamic Republic of", lat: 32, lng: 53, color: "#06b6d4" },
    IS: { name: "Iceland", lat: 65, lng: -18, color: "#8b5cf6" },
    IT: { name: "Italy", lat: 42.8333, lng: 12.8333, color: "#3b82f6" },
    JE: { name: "Jersey", lat: 49.21, lng: -2.13, color: "#06b6d4" },
    JM: { name: "Jamaica", lat: 18.25, lng: -77.5, color: "#f59e0b" },
    JO: { name: "Jordan", lat: 31, lng: 36, color: "#14b8a6" },
    JP: { name: "Japan", lat: 36, lng: 138, color: "#8b5cf6" },
    KE: { name: "Kenya", lat: 1, lng: 38, color: "#10b981" },
    KG: { name: "Kyrgyzstan", lat: 41, lng: 75, color: "#06b6d4" },
    KH: { name: "Cambodia", lat: 13, lng: 105, color: "#06b6d4" },
    KI: { name: "Kiribati", lat: 1.4167, lng: 173, color: "#14b8a6" },
    KM: { name: "Comoros", lat: -12.1667, lng: 44.25, color: "#14b8a6" },
    KN: { name: "Saint Kitts and Nevis", lat: 17.3333, lng: -62.75, color: "#f43f5e" },
    KP: { name: "Korea, Democratic People's Republic of", lat: 40, lng: 127, color: "#14b8a6" },
    KR: { name: "Korea, Republic of", lat: 37, lng: 127.5, color: "#8b5cf6" },
    KW: { name: "Kuwait", lat: 29.3375, lng: 47.6581, color: "#14b8a6" },
    KY: { name: "Cayman Islands", lat: 19.5, lng: -80.5, color: "#06b6d4" },
    KZ: { name: "Kazakhstan", lat: 48, lng: 68, color: "#10b981" },
    LA: { name: "Lao People's Democratic Republic", lat: 18, lng: 105, color: "#f59e0b" },
    LB: { name: "Lebanon", lat: 33.8333, lng: 35.8333, color: "#10b981" },
    LC: { name: "Saint Lucia", lat: 13.8833, lng: -61.1333, color: "#ec4899" },
    LI: { name: "Liechtenstein", lat: 47.1667, lng: 9.5333, color: "#14b8a6" },
    LK: { name: "Sri Lanka", lat: 7, lng: 81, color: "#ec4899" },
    LR: { name: "Liberia", lat: 6.5, lng: -9.5, color: "#f43f5e" },
    LS: { name: "Lesotho", lat: -29.5, lng: 28.5, color: "#8b5cf6" },
    LT: { name: "Lithuania", lat: 56, lng: 24, color: "#10b981" },
    LU: { name: "Luxembourg", lat: 49.75, lng: 6.1667, color: "#ec4899" },
    LV: { name: "Latvia", lat: 57, lng: 25, color: "#ec4899" },
    LY: { name: "Libyan Arab Jamahiriya", lat: 25, lng: 17, color: "#3b82f6" },
    MA: { name: "Morocco", lat: 32, lng: -5, color: "#f59e0b" },
    MC: { name: "Monaco", lat: 43.7333, lng: 7.4, color: "#f43f5e" },
    MD: { name: "Moldova, Republic of", lat: 47, lng: 29, color: "#f59e0b" },
    ME: { name: "Montenegro", lat: 42, lng: 19, color: "#ec4899" },
    MG: { name: "Madagascar", lat: -20, lng: 47, color: "#f43f5e" },
    MH: { name: "Marshall Islands", lat: 9, lng: 168, color: "#f43f5e" },
    MK: { name: "Macedonia, the former Yugoslav Republic of", lat: 41.8333, lng: 22, color: "#ec4899" },
    ML: { name: "Mali", lat: 17, lng: -4, color: "#14b8a6" },
    MM: { name: "Myanmar", lat: 22, lng: 98, color: "#3b82f6" },
    MN: { name: "Mongolia", lat: 46, lng: 105, color: "#ec4899" },
    MO: { name: "Macao", lat: 22.1667, lng: 113.55, color: "#8b5cf6" },
    MP: { name: "Northern Mariana Islands", lat: 15.2, lng: 145.75, color: "#f59e0b" },
    MQ: { name: "Martinique", lat: 14.6667, lng: -61, color: "#f43f5e" },
    MR: { name: "Mauritania", lat: 20, lng: -12, color: "#ec4899" },
    MS: { name: "Montserrat", lat: 16.75, lng: -62.2, color: "#f43f5e" },
    MT: { name: "Malta", lat: 35.8333, lng: 14.5833, color: "#06b6d4" },
    MU: { name: "Mauritius", lat: -20.2833, lng: 57.55, color: "#06b6d4" },
    MV: { name: "Maldives", lat: 3.25, lng: 73, color: "#06b6d4" },
    MW: { name: "Malawi", lat: -13.5, lng: 34, color: "#f43f5e" },
    MX: { name: "Mexico", lat: 23, lng: -102, color: "#f43f5e" },
    MY: { name: "Malaysia", lat: 2.5, lng: 112.5, color: "#06b6d4" },
    MZ: { name: "Mozambique", lat: -18.25, lng: 35, color: "#10b981" },
    NA: { name: "Namibia", lat: -22, lng: 17, color: "#ec4899" },
    NC: { name: "New Caledonia", lat: -21.5, lng: 165.5, color: "#ec4899" },
    NE: { name: "Niger", lat: 16, lng: 8, color: "#f59e0b" },
    NF: { name: "Norfolk Island", lat: -29.0333, lng: 167.95, color: "#8b5cf6" },
    NG: { name: "Nigeria", lat: 10, lng: 8, color: "#14b8a6" },
    NI: { name: "Nicaragua", lat: 13, lng: -85, color: "#06b6d4" },
    NL: { name: "Netherlands", lat: 52.5, lng: 5.75, color: "#ec4899" },
    NO: { name: "Norway", lat: 62, lng: 10, color: "#8b5cf6" },
    NP: { name: "Nepal", lat: 28, lng: 84, color: "#f59e0b" },
    NR: { name: "Nauru", lat: -0.5333, lng: 166.9167, color: "#10b981" },
    NU: { name: "Niue", lat: -19.0333, lng: -169.8667, color: "#06b6d4" },
    NZ: { name: "New Zealand", lat: -41, lng: 174, color: "#f43f5e" },
    OM: { name: "Oman", lat: 21, lng: 57, color: "#8b5cf6" },
    PA: { name: "Panama", lat: 9, lng: -80, color: "#ec4899" },
    PE: { name: "Peru", lat: -10, lng: -76, color: "#06b6d4" },
    PF: { name: "French Polynesia", lat: -15, lng: -140, color: "#10b981" },
    PG: { name: "Papua New Guinea", lat: -6, lng: 147, color: "#06b6d4" },
    PH: { name: "Philippines", lat: 13, lng: 122, color: "#f59e0b" },
    PK: { name: "Pakistan", lat: 30, lng: 70, color: "#f59e0b" },
    PL: { name: "Poland", lat: 52, lng: 20, color: "#f59e0b" },
    PM: { name: "Saint Pierre and Miquelon", lat: 46.8333, lng: -56.3333, color: "#3b82f6" },
    PN: { name: "Pitcairn", lat: -24.7, lng: -127.4, color: "#8b5cf6" },
    PR: { name: "Puerto Rico", lat: 18.25, lng: -66.5, color: "#14b8a6" },
    PS: { name: "Palestine", lat: 32, lng: 35.25, color: "#06b6d4" },
    PT: { name: "Portugal", lat: 39.5, lng: -8, color: "#06b6d4" },
    PW: { name: "Palau", lat: 7.5, lng: 134.5, color: "#8b5cf6" },
    PY: { name: "Paraguay", lat: -23, lng: -58, color: "#f43f5e" },
    QA: { name: "Qatar", lat: 25.5, lng: 51.25, color: "#06b6d4" },
    RE: { name: "Réunion", lat: -21.1, lng: 55.6, color: "#10b981" },
    RO: { name: "Romania", lat: 46, lng: 25, color: "#14b8a6" },
    RS: { name: "Serbia", lat: 44, lng: 21, color: "#10b981" },
    RU: { name: "Russian Federation", lat: 60, lng: 100, color: "#14b8a6" },
    RW: { name: "Rwanda", lat: -2, lng: 30, color: "#f43f5e" },
    SA: { name: "Saudi Arabia", lat: 25, lng: 45, color: "#14b8a6" },
    SB: { name: "Solomon Islands", lat: -8, lng: 159, color: "#8b5cf6" },
    SC: { name: "Seychelles", lat: -4.5833, lng: 55.6667, color: "#8b5cf6" },
    SD: { name: "Sudan", lat: 15, lng: 30, color: "#14b8a6" },
    SE: { name: "Sweden", lat: 62, lng: 15, color: "#f43f5e" },
    SG: { name: "Singapore", lat: 1.3667, lng: 103.8, color: "#f43f5e" },
    SH: { name: "Saint Helena, Ascension and Tristan da Cunha", lat: -15.9333, lng: -5.7, color: "#10b981" },
    SI: { name: "Slovenia", lat: 46, lng: 15, color: "#06b6d4" },
    SJ: { name: "Svalbard and Jan Mayen", lat: 78, lng: 20, color: "#10b981" },
    SK: { name: "Slovakia", lat: 48.6667, lng: 19.5, color: "#14b8a6" },
    SL: { name: "Sierra Leone", lat: 8.5, lng: -11.5, color: "#14b8a6" },
    SM: { name: "San Marino", lat: 43.7667, lng: 12.4167, color: "#14b8a6" },
    SN: { name: "Senegal", lat: 14, lng: -14, color: "#f59e0b" },
    SO: { name: "Somalia", lat: 10, lng: 49, color: "#f43f5e" },
    SR: { name: "Suriname", lat: 4, lng: -56, color: "#ec4899" },
    ST: { name: "Sao Tome and Principe", lat: 1, lng: 7, color: "#f59e0b" },
    SV: { name: "El Salvador", lat: 13.8333, lng: -88.9167, color: "#f43f5e" },
    SY: { name: "Syrian Arab Republic", lat: 35, lng: 38, color: "#06b6d4" },
    SZ: { name: "Swaziland", lat: -26.5, lng: 31.5, color: "#8b5cf6" },
    TC: { name: "Turks and Caicos Islands", lat: 21.75, lng: -71.5833, color: "#14b8a6" },
    TD: { name: "Chad", lat: 15, lng: 19, color: "#14b8a6" },
    TF: { name: "French Southern Territories", lat: -43, lng: 67, color: "#f59e0b" },
    TG: { name: "Togo", lat: 8, lng: 1.1667, color: "#10b981" },
    TH: { name: "Thailand", lat: 15, lng: 100, color: "#f59e0b" },
    TJ: { name: "Tajikistan", lat: 39, lng: 71, color: "#f59e0b" },
    TK: { name: "Tokelau", lat: -9, lng: -172, color: "#ec4899" },
    TL: { name: "Timor-Leste", lat: -8.55, lng: 125.5167, color: "#10b981" },
    TM: { name: "Turkmenistan", lat: 40, lng: 60, color: "#8b5cf6" },
    TN: { name: "Tunisia", lat: 34, lng: 9, color: "#06b6d4" },
    TO: { name: "Tonga", lat: -20, lng: -175, color: "#f43f5e" },
    TR: { name: "Turkey", lat: 39, lng: 35, color: "#8b5cf6" },
    TT: { name: "Trinidad and Tobago", lat: 11, lng: -61, color: "#3b82f6" },
    TV: { name: "Tuvalu", lat: -8, lng: 178, color: "#ec4899" },
    TW: { name: "Taiwan, Province of China", lat: 23.5, lng: 121, color: "#06b6d4" },
    TZ: { name: "Tanzania, United Republic of", lat: -6, lng: 35, color: "#f59e0b" },
    UA: { name: "Ukraine", lat: 49, lng: 32, color: "#14b8a6" },
    UG: { name: "Uganda", lat: 1, lng: 32, color: "#14b8a6" },
    UM: { name: "United States Minor Outlying Islands", lat: 19.2833, lng: 166.6, color: "#8b5cf6" },
    US: { name: "United States", lat: 38, lng: -97, color: "#14b8a6" },
    UY: { name: "Uruguay", lat: -33, lng: -56, color: "#3b82f6" },
    UZ: { name: "Uzbekistan", lat: 41, lng: 64, color: "#10b981" },
    VA: { name: "Holy See (Vatican City State)", lat: 41.9, lng: 12.45, color: "#06b6d4" },
    VC: { name: "Saint Vincent and the Grenadines", lat: 13.25, lng: -61.2, color: "#10b981" },
    VE: { name: "Venezuela, Bolivarian Republic of", lat: 8, lng: -66, color: "#06b6d4" },
    VG: { name: "Virgin Islands, British", lat: 18.5, lng: -64.5, color: "#14b8a6" },
    VI: { name: "Virgin Islands, U.S.", lat: 18.3333, lng: -64.8333, color: "#06b6d4" },
    VN: { name: "Viet Nam", lat: 16, lng: 106, color: "#f43f5e" },
    VU: { name: "Vanuatu", lat: -16, lng: 167, color: "#10b981" },
    WF: { name: "Wallis and Futuna", lat: -13.3, lng: -176.2, color: "#10b981" },
    WS: { name: "Samoa", lat: -13.5833, lng: -172.3333, color: "#f59e0b" },
    YE: { name: "Yemen", lat: 15, lng: 48, color: "#14b8a6" },
    YT: { name: "Mayotte", lat: -12.8333, lng: 45.1667, color: "#14b8a6" },
    ZA: { name: "South Africa", lat: -29, lng: 24, color: "#f59e0b" },
    ZM: { name: "Zambia", lat: -15, lng: 30, color: "#8b5cf6" },
    ZW: { name: "Zimbabwe", lat: -20, lng: 30, color: "#3b82f6" },
};


type CountryFeature = {
    type: "Feature";
    properties?: { name?: string };
};

type Source = {
    name: string;
    lat: number;
    lng: number;
    count: number;
    color: string;
    topIp: string;
    dominantTtp: string;
    topHassh: string;
    countryCode: string;
};

function tooltipFor(source: Source, event: MouseEvent<SVGElement>): TooltipState {
    const hasshLabel = source.topHassh && source.topHassh.length > 4 ? source.topHassh : "Scanning...";
    return {
        title: `Attacker Node: ${source.name}`,
        subtitle: "Active Botnet Infrastructure",
        details: [
            { label: "Top IP", value: source.topIp },
            { label: "Dom. TTP", value: source.dominantTtp },
            { label: "HASSH", value: hasshLabel },
        ],
        x: event.clientX,
        y: event.clientY,
    };
}
const MAP_NAME_TO_CC: Record<string, string> = {
    "united states of america": "US",
    "united states": "US",
    "usa": "US",
    "russia": "RU",
    "russian federation": "RU",
    "china": "CN",
    "indonesia": "ID",
    "india": "IN",
    "brazil": "BR",
    "vietnam": "VN",
    "viet nam": "VN",
    "iran": "IR",
    "iran, islamic republic of": "IR",
    "united kingdom": "GB",
    "great britain": "GB",
    "uk": "GB",
    "north korea": "KP",
    "south korea": "KR",
    "korea, republic of": "KR",
    "taiwan": "TW",
    "taiwan, province of china": "TW",
    "tanzania": "TZ",
    "tanzania, united republic of": "TZ",
    "moldova": "MD",
    "moldova, republic of": "MD",
    "bolivia": "BO",
    "bolivia, plurinational state of": "BO",
    "syria": "SY",
    "syrian arab republic": "SY",
    "venezuela": "VE",
    "venezuela, bolivarian republic of": "VE",
    "laos": "LA",
    "lao people's democratic republic": "LA",
    "brunei": "BN",
    "brunei darussalam": "BN",
    "dem. rep. congo": "CD",
    "congo, the democratic republic of the": "CD",
    "congo": "CG",
    "w. sahara": "EH",
    "western sahara": "EH",
    "south africa": "ZA",
    "greenland": "GL",
    "timor-leste": "TL",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "israel": "IL",
    "palestine": "PS",
    "gambia": "GM",
    "algeria": "DZ",
    "jordan": "JO",
    "united arab emirates": "AE",
    "qatar": "QA",
    "kuwait": "KW",
    "iraq": "IQ",
    "oman": "OM",
    "vanuatu": "VU",
    "cambodia": "KH",
    "thailand": "TH",
    "myanmar": "MM",
    "bangladesh": "BD",
    "bhutan": "BT",
    "nepal": "NP",
    "pakistan": "PK",
    "afghanistan": "AF",
    "tajikistan": "TJ",
    "kyrgyzstan": "KG",
    "turkmenistan": "TM",
    "armenia": "AM",
    "sweden": "SE",
    "belarus": "BY",
    "ukraine": "UA",
    "poland": "PL",
    "austria": "AT",
    "hungary": "HU",
    "romania": "RO",
    "lithuania": "LT",
    "latvia": "LV",
    "estonia": "EE",
    "germany": "DE",
    "bulgaria": "BG",
    "greece": "GR",
    "turkey": "TR",
    "albania": "AL",
    "croatia": "HR",
    "switzerland": "CH",
    "luxembourg": "LU",
    "belgium": "BE",
    "netherlands": "NL",
    "portugal": "PT",
    "spain": "ES",
    "ireland": "IE",
    "new caledonia": "NC",
    "solomon is.": "SB",
    "new zealand": "NZ",
    "australia": "AU",
    "sri lanka": "LK",
    "italy": "IT",
    "denmark": "DK",
    "azerbaijan": "AZ",
    "georgia": "GE",
    "philippines": "PH",
    "malaysia": "MY",
    "slovenia": "SI",
    "finland": "FI",
    "slovakia": "SK",
    "czechia": "CZ",
    "czech republic": "CZ",
    "eritrea": "ER",
    "japan": "JP",
    "paraguay": "PY",
    "yemen": "YE",
    "saudi arabia": "SA",
    "morocco": "MA",
    "egypt": "EG",
    "libya": "LY",
    "libyan arab jamahiriya": "LY",
    "ethiopia": "ET",
    "djibouti": "DJ",
    "uganda": "UG",
    "rwanda": "RW",
    "bosnia and herz.": "BA",
    "bosnia and herzegovina": "BA",
    "macedonia": "MK",
    "macedonia, the former yugoslav republic of": "MK",
    "serbia": "RS",
    "montenegro": "ME",
    "france": "FR",
    "falkland is.": "FK",
    "fr. s. antarctic lands": "TF",
    "central african rep.": "CF",
    "dominican rep.": "DO"
};

function getCountryCode(name: string): string {
    const lower = name.toLowerCase();
    if (MAP_NAME_TO_CC[lower]) return MAP_NAME_TO_CC[lower];
    const foundKey = Object.keys(COUNTRY_COORDS).find(k => {
        const cName = COUNTRY_COORDS[k].name.toLowerCase();
        return cName === lower || cName.includes(lower) || lower.includes(cName);
    });
    return foundKey || "";
}

export default function ThreatMap({ onRegionClick, selectedRegion, underAttack = false, threatLogs: externalLogs }: ThreatMapProps = {}) {
    const { theme } = useTheme();
    const [isExpanded, setIsExpanded] = useState(false);
    const [tooltipContent, setTooltipContent] = useState<TooltipState | null>(null);
    const [countries, setCountries] = useState<CountryFeature[]>([]);
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;

    useEffect(() => {
        let cancelled = false;
        fetch("/world-atlas.json")
            .then((response) => response.json())
            .then((topology) => {
                if (cancelled) {
                    return;
                }
                const collection = feature(topology, topology.objects.countries) as unknown as {
                    features: CountryFeature[];
                };
                setCountries(collection.features);
            })
            .catch(() => setCountries([]));

        return () => {
            cancelled = true;
        };
    }, []);

    const projection = useMemo(
        () =>
            geoEqualEarth()
                .fitExtent(
                    [
                        [12, 18],
                        [WIDTH - 12, HEIGHT - 18],
                    ],
                    { type: "Sphere" },
                ),
        [],
    );
    const path = useMemo(() => geoPath(projection), [projection]);
    const graticule = useMemo(() => geoGraticule().step([30, 30])(), []);

    const project = useMemo(() => (lng: number, lat: number) => {
        const point = projection([lng, lat]) ?? [WIDTH / 2, HEIGHT / 2];
        return { x: point[0], y: point[1] };
    }, [projection]);

    const targetPoint = useMemo(() => project(TARGET.lng, TARGET.lat), [project]);
    const mapData = useMemo<Source[]>(() => {
        const grouped = new Map<string, Source>();
        for (const log of threatLogs) {
            if (!log.country || log.country === "XX") {
                continue;
            }
            const meta = COUNTRY_COORDS[log.country];
            const hasCoordinates = typeof log.latitude === "number" && typeof log.longitude === "number";
            if (!meta && !hasCoordinates) {
                continue;
            }
            const countryMeta = meta ?? {
                name: log.countryName ?? log.country,
                lat: log.latitude as number,
                lng: log.longitude as number,
                color: "#38bdf8",
            };
            const current = grouped.get(log.country) ?? {
                ...countryMeta,
                countryCode: log.country,
                count: 0,
                topIp: log.ip,
                dominantTtp: log.mitreId || log.type,
                topHassh: "",
            };
            current.count += 1;
            if (log.hassh && log.hassh.length > 4 && (!current.topHassh || current.topHassh === "N/A" || current.topHassh === "unknown")) {
                current.topHassh = log.hassh;
            }
            // Always center on the country if defined in COUNTRY_COORDS, otherwise use IP coordinates
            if (!meta && hasCoordinates) {
                current.lat = log.latitude as number;
                current.lng = log.longitude as number;
            }
            if (!current.topIp || current.topIp === "0.0.0.0") {
                current.topIp = log.ip;
            }
            grouped.set(log.country, current);
        }
        return [...grouped.values()];
    }, [threatLogs]);
    const sources = useMemo(() => {
        return mapData.map((source) => {
            const start = project(source.lng, source.lat);
            const midX = (start.x + targetPoint.x) / 2;
            const midY = (start.y + targetPoint.y) / 2;
            const distance = Math.hypot(targetPoint.x - start.x, targetPoint.y - start.y);
            const path = `M ${start.x},${start.y} Q ${midX},${midY - distance * 0.18} ${targetPoint.x},${targetPoint.y}`;
            return { ...source, point: start, path };
        });
    }, [mapData, project, targetPoint]);

    const selectedCC = useMemo(() => {
        if (!selectedRegion) return null;
        const matchedSource = sources.find(s => s.topIp === selectedRegion);
        if (matchedSource) return matchedSource.countryCode;
        if (selectedRegion.length === 2) return selectedRegion.toUpperCase();
        return getCountryCode(selectedRegion);
    }, [selectedRegion, sources]);

    const land = theme === "dark" ? "#171717" : "#dbeafe";
    const selectedLand = theme === "dark" ? "#2563eb" : "#3b82f6";
    const landStroke = theme === "dark" ? "#2f3747" : "#ffffff";
    const ocean = theme === "dark" ? "#050505" : "#f8fafc";

    const selectSource = useCallback((sourceName: string, topIp: string) => {
        onRegionClick?.(selectedRegion === topIp ? null : topIp);
    }, [onRegionClick, selectedRegion]);

    const renderSources = useMemo(() => {
        if (!underAttack) return null;
        return sources.map((source, index) => {
            const isDimmed = selectedRegion && selectedRegion !== source.name && selectedRegion !== source.topIp;
            const isLeftOfTarget = source.point.x < targetPoint.x;
            return (
                <g key={source.name} opacity={isDimmed ? 0.25 : 1}>
                    <path
                        d={source.path}
                        fill="none"
                        stroke={source.color}
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeDasharray="4,4"
                        style={{ animation: `dash ${2 + index * 0.3}s linear infinite` }}
                    />
                    <text
                        x={source.point.x + (isLeftOfTarget ? -10 : 10)}
                        y={source.point.y + 3}
                        textAnchor={isLeftOfTarget ? "end" : "start"}
                        fill={theme === "dark" ? "#dbeafe" : "#1e3a8a"}
                        fontSize="10"
                        fontWeight="700"
                        paintOrder="stroke"
                        stroke={theme === "dark" ? "#050505" : "#f8fafc"}
                        strokeWidth="4"
                    >
                        {source.name}
                    </text>
                    <g
                        role="button"
                        tabIndex={0}
                        onClick={() => selectSource(source.name, source.topIp)}
                        onMouseEnter={(event) => setTooltipContent(tooltipFor(source, event))}
                        onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                        onMouseLeave={() => setTooltipContent(null)}
                        className="cursor-pointer"
                    >
                        <circle cx={source.point.x} cy={source.point.y} r="16" fill="transparent" />
                        <circle cx={source.point.x} cy={source.point.y} r="8" fill={source.color} opacity="0.2" />
                        <circle cx={source.point.x} cy={source.point.y} r="4" fill={source.color} className="animate-pulse" />
                        <circle cx={source.point.x} cy={source.point.y} r="3" fill={source.color} />
                    </g>
                </g>
            );
        });
    }, [underAttack, sources, selectedRegion, theme, selectSource, targetPoint]);

    return (
        <>
            {isExpanded && (
                <div className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={() => setIsExpanded(false)} />
            )}
            <div className={isExpanded
                ? "fixed inset-0 m-auto w-[95vw] h-[90vh] z-[100] origin-center bg-slate-50 dark:bg-[#050505] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-center animate-in zoom-in-95 fade-in duration-200"
                : "relative w-full h-full flex flex-col bg-slate-50 dark:bg-[#050505] overflow-hidden group"}>
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`absolute top-4 right-4 z-[80] bg-black/60 hover:bg-black p-2 rounded-lg text-white backdrop-blur border border-white/10 transition-all ${isExpanded ? "opacity-100 scale-100" : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"}`}
                    title={isExpanded ? "Collapse Map" : "Expand Map"}
                >
                    {isExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </button>

                <div className={`relative flex-1 w-full flex overflow-hidden ${isExpanded ? "items-center justify-center p-2 md:p-12 mb-12 md:mb-0" : ""}`}>
                    <div className="absolute inset-0 opacity-20 pointer-events-none"
                        style={{
                            backgroundImage: `radial-gradient(${theme === "dark" ? "#333" : "#ccc"} 1px, transparent 1px)`,
                            backgroundSize: "20px 20px",
                        }}>
                    </div>

                    <svg className="relative z-10 w-full h-full" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="CloudSentinel global threat map">
                        <rect width={WIDTH} height={HEIGHT} fill={ocean} />
                        <path
                            d={path(graticule) ?? undefined}
                            fill="none"
                            stroke={theme === "dark" ? "#1f2937" : "#cbd5e1"}
                            strokeWidth="0.45"
                            opacity="0.55"
                        />
                        <g stroke={landStroke} strokeWidth="0.65">
                            {countries.map((country) => {
                                const name = country.properties?.name ?? "";
                                const cc = getCountryCode(name);
                                const selected = !!selectedCC && selectedCC === cc;
                                return (
                                    <path
                                        key={name}
                                        d={path(country as never) ?? undefined}
                                        fill={selected ? selectedLand : land}
                                        opacity={selectedRegion && !selected ? 0.35 : 0.92}
                                        onClick={() => {
                                            if (!cc) return;
                                            const source = sources.find(s => s.countryCode === cc);
                                            const val = source?.topIp || cc;
                                            onRegionClick?.(selectedRegion === val ? null : val);
                                        }}
                                        className={`cursor-pointer transition-colors duration-200 ${!selected ? "hover:fill-blue-500/10 dark:hover:fill-blue-400/10" : ""}`}
                                    >
                                        <title>{name}</title>
                                    </path>
                                );
                            })}
                        </g>

                        {renderSources}

                        <g
                            onMouseEnter={(event) => setTooltipContent({ title: TARGET.name, subtitle: "Local Honeypot Target", x: event.clientX, y: event.clientY })}
                            onMouseMove={(event) => setTooltipContent((previous) => previous ? { ...previous, x: event.clientX, y: event.clientY } : null)}
                            onMouseLeave={() => setTooltipContent(null)}
                        >
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="10" fill="rgba(0, 255, 65, 0.25)" stroke="#00ff41" />
                            <circle cx={targetPoint.x} cy={targetPoint.y} r="4" fill="#00ff41" className="animate-pulse" />
                        </g>
                    </svg>



                    <div className={`absolute left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded border border-white/10 flex flex-col gap-1 z-[60] pointer-events-none ${isExpanded ? "top-8 md:top-12 md:left-12" : "top-4"}`}>
                        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">Global Defcon</span>
                        <span className="text-xl font-bold font-mono text-white flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${underAttack ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`}></span>
                            {underAttack ? "UNDER ATTACK" : "MONITORING"}
                        </span>
                    </div>

                    {tooltipContent && (
                        <div
                            className="fixed z-[120] bg-slate-900/95 backdrop-blur-md text-slate-100 px-3 py-2 rounded-lg border border-slate-700 shadow-2xl pointer-events-none transform -translate-x-1/2 -translate-y-full mt-[-15px] min-w-[220px] max-w-[280px]"
                            style={{ left: tooltipContent.x, top: tooltipContent.y }}
                        >
                            <div className="flex flex-col gap-0.5 mb-2">
                                <span className="font-bold text-sm text-white">{tooltipContent.title}</span>
                                {tooltipContent.subtitle && <span className="text-[10px] text-red-400 uppercase tracking-widest font-semibold">{tooltipContent.subtitle}</span>}
                            </div>

                            {tooltipContent.details && tooltipContent.details.length > 0 && (
                                <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-700/50">
                                    {tooltipContent.details.map((detail, idx) => (
                                        <div key={idx} className="flex justify-between items-center text-xs">
                                            <span className="text-slate-400 font-medium">{detail.label}:</span>
                                            <span className="font-mono text-blue-300 ml-3 truncate max-w-[120px]">{detail.value}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
                {!isExpanded && (
                    <div className="relative border-t border-slate-300 dark:border-white/10 bg-white dark:bg-[#050505] overflow-hidden text-[11px] shrink-0 z-[999] w-full flex items-center h-10">
                        <style>{`
                            @keyframes marquee {
                                0% { transform: translateX(0); }
                                100% { transform: translateX(-50%); }
                            }
                        `}</style>
                        <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center pl-3 pr-8 bg-gradient-to-r from-white via-white to-transparent dark:from-[#050505] dark:via-[#050505] dark:to-transparent">
                            <span className="font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest shrink-0 flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span> Intel Feed
                            </span>
                        </div>
                        <div className="flex items-center gap-4 whitespace-nowrap opacity-80 animate-[marquee_20s_linear_infinite] hover:[animation-play-state:paused] pl-[140px]">
                            {threatLogs.length === 0 && <span className="text-slate-500">Awaiting initial sensor data stream...</span>}
                            {Array.from(new Map(threatLogs.map(log => [log.ip, log])).values()).slice(0, 10).map((log, i) => (
                                <span key={i} className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                                    <span className="font-mono text-blue-600 dark:text-blue-400">{log.ip}</span>
                                    <span>attempted</span>
                                    <span className="font-mono text-rose-500">{log.type}</span>
                                    <span>•</span>
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}
