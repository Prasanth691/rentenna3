module.exports = function(grunt) {

    var modules = [
        {
            name: 'admin',
            src: [
                'sass-config/development',
                'resource-src/jquery',
                'resource-src/map',
                'resource-src/bootstrap',
                'resource-src/web-base',
                'resource-src/web-admin',
                'resource-src/codemirror',
                'resource-src/abtest',
                'resource-src/quiz',
                'resource-src/base',
                'resource-src/client',
                'resource-src/admin'
            ]
        },
        {
            name: 'jsj',
            src: [
                'sass-config/development',
                'resource-src/jquery',
                'resource-src/web-base',
                'resource-src/base',
                'resource-src/jsj'
            ]
        },
    ]

    if(process.env.ENVIRONMENT == 'development')
        modules.push({
            name: 'client-development',
            src: [
                'sass-config/development',
                'resource-src/jquery',
                'resource-src/map',
                'resource-src/web-base',
                'resource-src/quiz',
                'resource-src/validation',
                'resource-src/base',
                'resource-src/client'
            ]
        })
    else if(process.env.ENVIRONMENT == 'qa')
        modules.push({
            name: 'client-qa',
            src: [
                'sass-config/qa',
                'resource-src/jquery',
                'resource-src/map',
                'resource-src/web-base',
                'resource-src/quiz',
                'resource-src/validation',
                'resource-src/base',
                'resource-src/client'
            ]
        })
    else if(process.env.ENVIRONMENT == 'staging')
        modules.push({
            name: 'client-staging',
            src: [
                'sass-config/staging',
                'resource-src/jquery',
                'resource-src/map',
                'resource-src/web-base',
                'resource-src/quiz',
                'resource-src/validation',
                'resource-src/base',
                'resource-src/client'
            ]
        })
    else if(process.env.ENVIRONMENT == 'production')
        modules.push({
            name: 'client-production',
            src: [
                'sass-config/production',
                'resource-src/jquery',
                'resource-src/map',
                'resource-src/web-base',
                'resource-src/quiz',
                'resource-src/validation',
                'resource-src/base',
                'resource-src/client'
            ]
        })

    // Project configuration
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),
        web: {
            appengine_modules: ['appdev.yaml', 'reporting.yaml'],
            appengine_port: 8089,
            appengine_admin_port: 8009,
            interim_dir: 'resource-interim',
            output_dir: 'resource/compiled',
            datastore: '../datastore',
            blobstore: '../blobstore',
            modules: modules,
        },
    });

    grunt.loadNpmTasks('grunt-web-rentenna3');

};
