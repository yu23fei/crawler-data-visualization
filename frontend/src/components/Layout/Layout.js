// frontend/src/components/Layout/Layout.js
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

const Layout = () => {
    return (
        <div style={styles.container}>
            <Sidebar />
            <div style={styles.main}>
                <Topbar />
                <div style={styles.content}>
                    <Outlet />
                </div>
            </div>
        </div>
    );
};

const styles = {
    container: {
        display: 'flex',
        minHeight: '100vh',
        background: '#f0f2f5'
    },
    main: {
        flex: 1,
        marginLeft: '220px',
        display: 'flex',
        flexDirection: 'column'
    },
    content: {
        flex: 1,
        padding: '0 32px 32px 32px'
    }
};

export default Layout;
