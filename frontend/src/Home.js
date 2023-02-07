import React from 'react';
import { Link } from 'react-router-dom';
import Layout from './Layout';

function Home() {
  return (
    <Layout>
      <ul>
        <li><Link to="/list-remotes">List Remotes</Link></li>
        <li><Link to="/list-ports">List Ports</Link></li>
        <li><Link to="/add-remote">Add Remote</Link></li>
      </ul>
    </Layout>
  );
}

export default Home;
