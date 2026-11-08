'use strict';
const publisher=process.env.RANK_PUBLISHER;
module.exports={
  appId:'cz.rankstudio.desktop',productName:'Rank Studio',copyright:'Rank Studio',
  directories:{output:'../release/windows',buildResources:'assets'},
  files:['main.cjs','preload.cjs','security.cjs','transport.cjs','updates.cjs','loading.html','theme.css','assets/icon.png','package.json',
    {from:'../build',to:'.',filter:['update-policy.json']}],
  extraResources:[{from:'../build/desktop-backend/rank-backend',to:'backend'}],
  asar:true,
  electronFuses:{runAsNode:false,enableNodeOptionsEnvironmentVariable:false,enableNodeCliInspectArguments:false,
    enableEmbeddedAsarIntegrityValidation:true,onlyLoadAppFromAsar:true,grantFileProtocolExtraPrivileges:false},
  forceCodeSigning:process.env.RANK_SIGNED_BUILD==='1',
  win:{target:[{target:'nsis',arch:['x64']}],icon:'assets/icon.ico',...(publisher?{publisherName:publisher}:{}),verifyUpdateCodeSignature:true,
       requestedExecutionLevel:'asInvoker',artifactName:'Rank-Studio-${version}-Setup.${ext}'},
  nsis:{oneClick:false,perMachine:false,allowToChangeInstallationDirectory:true,createDesktopShortcut:true,
        createStartMenuShortcut:true,shortcutName:'Rank Studio',deleteAppDataOnUninstall:false},
  publish:process.env.RANK_UPDATE_URL?{provider:'generic',url:process.env.RANK_UPDATE_URL}:null
};
