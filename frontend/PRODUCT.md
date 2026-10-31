# CivicMesh

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript. Use reusable components and maintainable architecture. Do not use Next.js. The citizen application is implemented with React Router, Leaflet and browser-backed typed mock adapters.

## Users

Everyday citizens reporting local civic problems, finding nearby issues, and gathering community attention around recurring problems. Examples include potholes, garbage accumulation, waterlogging, broken streetlights, and damaged roads.

## Product Purpose

Make it easier for citizens to report civic issues, build public awareness, and organize community participation. The hackathon prototype prioritizes a complete citizen experience across the landing page, interactive issue map, reporting, community campaigns, and profile.

## Positioning

CivicMesh brings location-based issue reporting and community campaigns into one citizen-facing experience. A unique competitive claim has not been established.

## Operating Context

Citizens explore an interactive city map, select a location, upload a photo, and optionally add a voice note or text description. They browse nearby reports, join or create campaigns around recurring problems, and track reports and contributions through their profile.

The responsive application is mobile-first and should feel app-like. Mobile uses bottom navigation; desktop uses a left sidebar.

## Capabilities and Constraints

- Deliver only the citizen-facing frontend for a hackathon prototype. Prioritize the landing page, interactive map, issue reporting, community campaigns, and user profile.
- Work within frontend-owned files on the feat/frontend branch. Do not modify backend services, APIs, database schemas, or teammates' files. This product record is scoped to the frontend application.
- Use realistic mock data where backend APIs are unavailable. Keep integration adaptable for future backend connection.
- Do not invent government integrations or claim official verification.
- Build incrementally and review each screen before proceeding to the next. Avoid unnecessary dependencies, enterprise features, and overengineering.
- Open decisions: target city, authentication behavior, map provider, campaign mechanics, report status definitions, and backend contracts.

## Brand Commitments

The product name is CivicMesh. The user requests a premium, modern, distinctive interface, purposeful animation, smooth transitions, and responsive layouts, avoiding generic AI-generated SaaS layouts. Approved identity: warm orange, beige/parchment, brown and cream; irregular hand-drawn accents. App screens prioritize readable forms and maps.

## Evidence on Hand

The repository contains a folder scaffold, team ownership documentation, and review configuration. No implemented citizen UI, real report dataset, official verification, government integration, or proof of outcomes has been provided. Prototype content must not be presented as real operational evidence.

## Product Principles

- Make reporting local issues easy and understandable.
- Connect individual reports with nearby community participation.
- Prioritize the core citizen journey within hackathon scope.
- Keep prototype data and integration claims honest.
- Preserve frontend ownership and make future API integration straightforward.

## Accessibility & Inclusion

Support keyboard navigation, readable contrast, clear labels, visible focus states, and reduced-motion preferences across responsive layouts.

## Current Delivery Scope

The application opens directly on Map. Landing-page implementation and animation are postponed. Navigation is exactly Map, Report and Campaigns, with a prominent central plus on mobile and a desktop sidebar. Profile access stays top-right at all widths. Report, campaign and profile data share local mock services; photographs and audio are stored in IndexedDB. No official verification or government integration is connected.
