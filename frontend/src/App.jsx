import React from 'react'
import { useLoaderData } from "react-router-dom";

export default function App() {
  let path = useLoaderData();

  console.log(path);

  return (
    <div>
      <h1>App { path }</h1>
    </div>
  )
}